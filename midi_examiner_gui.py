#!/usr/bin/env python3
"""
MIDI File Examiner — GUI Frontend
A PyQt6-based graphical interface for the MIDI File Examiner.
"""

import sys
import os
import io
import re
import contextlib

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget,
        QVBoxLayout, QHBoxLayout,
        QPushButton, QLineEdit, QTextEdit, QFileDialog, QTabWidget, QMenu,
        QListWidget, QListWidgetItem, QSplitter,
    )
    from PyQt6.QtGui import (QFont, QKeySequence, QAction,
                              QDragEnterEvent, QDropEvent,
                              QFileOpenEvent, QPalette, QColor)
    from PyQt6.QtCore import Qt, QEvent, QThread, QTimer, pyqtSignal
except ImportError:
    print("Error: PyQt6 is required. Install it with: pip install PyQt6")
    sys.exit(1)

# Ensure the directory containing this script is on the path so that
# midi_examiner and midi_patches_db can always be found.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from midi_examiner import __version__, analyze_midi_file, print_results

# Mapping from ALL-CAPS section titles (as printed) to shorter tab labels.
_TAB_LABELS = {
    "FILE INFORMATION": "File Info",
    "TIMING INFORMATION": "Timing",
    "METADATA": "Metadata",
    "TRACK INFORMATION": "Tracks",
    "TEXT EVENTS": "Text Events",
    "MARKERS": "Markers",
    "CUE POINTS": "Cue Points",
    "LYRICS": "Lyrics",
    "SYSTEM EXCLUSIVE (SYSEX) MESSAGES": "SysEx",
    "BANK SELECT MESSAGES": "Bank Select",
    "PROGRAM CHANGES": "Programs",
    "CONTROL CHANGES": "Control Changes",
}


# ── macOS Services integration ────────────────────────────────────────────────
#
# Qt's QTextEdit uses a custom QNSView (not NSTextView) which does not
# implement NSServicesMenuRequestor.  Without that protocol macOS never
# populates the Services menu for our view, so NSApp.servicesMenu() always
# returns 0 items.
#
# We fix this by ISA-swizzling each viewport NSView at creation time:
#   1. Allocate a new ObjC class that inherits from the existing view class.
#   2. Add writeSelectionToPasteboard:types: and validRequestorForSendType:
#      returnType: that delegate back to the Python QTextEdit instance.
#   3. Swap the view's isa pointer to the new class (object_setClass).
#   4. Register our app's send types with NSApp so macOS populates the menu.
#
# After this, NSApp.servicesMenu() returns the real system services for text,
# and we enumerate them to build the right-click Services submenu.

import weakref as _weakref

# Keep C-function-pointer IMPs alive (they must not be GC'd)
_svc_imp_refs: list = []
# Map NSView* (int) → weakref(QTextEdit)
_svc_view_map: dict = {}
# Map base_class pointer → new services-enabled class pointer
_svc_class_cache: dict = {}


def _objc_lib():
    import ctypes, ctypes.util
    lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
    lib.sel_registerName.restype = ctypes.c_void_p
    lib.sel_registerName.argtypes = [ctypes.c_char_p]
    lib.objc_getClass.restype  = ctypes.c_void_p
    lib.objc_getClass.argtypes = [ctypes.c_char_p]
    return lib


def _setup_services_menu():
    """Create an NSMenu, set it as the app Services menu, and ask pbs to populate it.

    Qt never calls -[NSApplication setServicesMenu:], so NSApp.servicesMenu
    returns nil and pbs never populates the menu with text services such as
    Translate or Look Up.  This function fixes that once at app startup.
    """
    try:
        import ctypes, ctypes.util
        lib = _objc_lib()

        def SEL(n):
            return lib.sel_registerName(n if isinstance(n, bytes) else n.encode())

        def msg0(obj, sel):
            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            return lib.objc_msgSend(obj, SEL(sel))

        def msg1(obj, sel, a):
            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            return lib.objc_msgSend(obj, SEL(sel), a)

        def msg2(obj, sel, a, b):
            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                          ctypes.c_void_p, ctypes.c_void_p]
            return lib.objc_msgSend(obj, SEL(sel), a, b)

        def nsstr(s):
            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
            return lib.objc_msgSend(lib.objc_getClass(b'NSString'),
                                    SEL(b'stringWithUTF8String:'), s.encode('utf-8'))

        NSApp = msg0(lib.objc_getClass(b'NSApplication'), b'sharedApplication')
        if not NSApp:
            return

        # Only set up once — if a services menu is already set, we're done.
        if msg0(NSApp, b'servicesMenu'):
            return

        # Create a new NSMenu (retain count = 1, we own it).
        NSMenu_cls = lib.objc_getClass(b'NSMenu')
        alloc = msg0(NSMenu_cls, b'alloc')
        if not alloc:
            return
        svc_menu = msg0(alloc, b'init')
        if not svc_menu:
            return

        # Hand it to NSApp — NSApp retains it (retain count becomes 2).
        msg1(NSApp, b'setServicesMenu:', svc_menu)

        # Release our ownership so retain count is 1 (held by NSApp only).
        msg0(svc_menu, b'release')

        # Register both UTI and legacy pasteboard types so all text services
        # (including "Look Up in Dictionary" which only accepts NSStringPboardType)
        # appear in the Services menu.
        NSMutableArray_cls = lib.objc_getClass(b'NSMutableArray')
        arr = msg0(NSMutableArray_cls, b'array')
        msg1(arr, b'addObject:', nsstr('public.utf8-plain-text'))
        msg1(arr, b'addObject:', nsstr('NSStringPboardType'))
        msg2(NSApp, b'registerServicesMenuSendTypes:returnTypes:', arr, arr)

        # Ask pbs to rebuild the services registry and populate our menu.
        ctypes.cdll.LoadLibrary(ctypes.util.find_library('AppKit')).NSUpdateDynamicServices()
    except Exception:
        pass


def _make_services_class(lib, base_class):
    """Build (once per base class) an ObjC subclass with NSServicesMenuRequestor."""
    import ctypes
    if base_class in _svc_class_cache:
        return _svc_class_cache[base_class]

    def SEL(n):
        return lib.sel_registerName(n if isinstance(n, bytes) else n.encode())

    def nsstr(s):
        lib.objc_msgSend.restype = ctypes.c_void_p
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        return lib.objc_msgSend(lib.objc_getClass(b'NSString'),
                                SEL(b'stringWithUTF8String:'), s.encode('utf-8'))

    def msg1(obj, sel, a):
        lib.objc_msgSend.restype = ctypes.c_void_p
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        return lib.objc_msgSend(obj, SEL(sel), a)

    def msg2(obj, sel, a, b):
        lib.objc_msgSend.restype = ctypes.c_void_p
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_void_p, ctypes.c_void_p]
        return lib.objc_msgSend(obj, SEL(sel), a, b)

    # --- validRequestorForSendType:returnType: ---
    # Returns self when sendType is plain-text (we can provide it), else nil.
    VALID_T = ctypes.CFUNCTYPE(ctypes.c_void_p,
                               ctypes.c_void_p, ctypes.c_void_p,
                               ctypes.c_void_p, ctypes.c_void_p)

    def _valid_requestor(self_ptr, _cmd, send_type, return_type):
        if send_type:
            lib.objc_msgSend.restype = ctypes.c_char_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            cs = lib.objc_msgSend(send_type, SEL(b'UTF8String'))
            lib.objc_msgSend.restype = ctypes.c_void_p
            if cs and b'utf8-plain-text' in cs:
                ref = _svc_view_map.get(self_ptr)
                if ref:
                    w = ref()
                    if w and w.textCursor().hasSelection():
                        return self_ptr
        return 0

    valid_imp = VALID_T(_valid_requestor)

    # --- writeSelectionToPasteboard:types: ---
    # Writes the current selection to the pasteboard so the service can read it.
    WRITE_T = ctypes.CFUNCTYPE(ctypes.c_bool,
                               ctypes.c_void_p, ctypes.c_void_p,
                               ctypes.c_void_p, ctypes.c_void_p)

    def _write_selection(self_ptr, _cmd, pboard, types):
        ref = _svc_view_map.get(self_ptr)
        if not ref:
            return False
        w = ref()
        if not w:
            return False
        text = w.textCursor().selectedText()
        if not text:
            return False
        # Declare both the modern UTI and the legacy NSStringPboardType so that
        # services like "Look Up in Dictionary" (which only accepts the legacy
        # NSStringPboardType) can read the pasteboard.
        type_uti    = nsstr('public.utf8-plain-text')
        type_legacy = nsstr('NSStringPboardType')
        NSMutableArray_cls = lib.objc_getClass(b'NSMutableArray')
        lib.objc_msgSend.restype  = ctypes.c_void_p
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        alloc = lib.objc_msgSend(NSMutableArray_cls, SEL(b'alloc'))
        arr   = lib.objc_msgSend(alloc,              SEL(b'init'))
        lib.objc_msgSend.restype  = ctypes.c_void_p
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        lib.objc_msgSend(arr, SEL(b'addObject:'), type_uti)
        lib.objc_msgSend(arr, SEL(b'addObject:'), type_legacy)
        msg2(pboard, b'declareTypes:owner:', arr, None)
        msg2(pboard, b'setString:forType:', nsstr(text), type_uti)
        msg2(pboard, b'setString:forType:', nsstr(text), type_legacy)
        lib.objc_msgSend.restype  = ctypes.c_void_p
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.objc_msgSend(arr, SEL(b'release'))
        return True

    write_imp = WRITE_T(_write_selection)
    _svc_imp_refs.extend([valid_imp, write_imp])  # prevent GC

    # Allocate new class
    lib.objc_allocateClassPair.restype  = ctypes.c_void_p
    lib.objc_allocateClassPair.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_ulong]
    class_name = f'_METextView_{base_class}'.encode()
    new_cls = lib.objc_allocateClassPair(base_class, class_name, 0)
    if not new_cls:
        # Already registered — get existing
        new_cls = lib.objc_getClass(class_name)
        _svc_class_cache[base_class] = new_cls
        return new_cls

    lib.class_addMethod.restype  = ctypes.c_bool
    lib.class_addMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                     ctypes.c_void_p, ctypes.c_char_p]
    lib.class_addMethod(new_cls, SEL(b'validRequestorForSendType:returnType:'),
                        valid_imp, b'@@:@@')
    lib.class_addMethod(new_cls, SEL(b'writeSelectionToPasteboard:types:'),
                        write_imp, b'B@:@@')

    lib.objc_registerClassPair.argtypes = [ctypes.c_void_p]
    lib.objc_registerClassPair(new_cls)

    _svc_class_cache[base_class] = new_cls
    return new_cls


def _register_view_for_services(widget):
    """ISA-swizzle the viewport NSView so macOS recognises it as a text provider."""
    try:
        import ctypes
        lib = _objc_lib()
        lib.object_getClass.restype  = ctypes.c_void_p
        lib.object_getClass.argtypes = [ctypes.c_void_p]
        lib.object_setClass.restype  = ctypes.c_void_p
        lib.object_setClass.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        ns_view    = int(widget.viewport().winId())
        base_class = lib.object_getClass(ns_view)
        new_cls    = _make_services_class(lib, base_class)
        if not new_cls:
            return
        lib.object_setClass(ns_view, new_cls)
        _svc_view_map[ns_view] = _weakref.ref(widget)
    except Exception:
        pass


def _open_translation(text):
    """Open macOS system translation for the given text.

    On macOS 12+, "Translate" is a built-in NSTextView feature (not a
    traditional NSService), so it never appears in the pbs Services menu.
    We invoke it by sending _translate: through the responder chain; if
    nothing handles it we fall back to opening Translate.app (if present)
    or the system browser.
    """
    import subprocess, urllib.parse
    try:
        import ctypes, ctypes.util
        lib = _objc_lib()

        def SEL(n):
            return lib.sel_registerName(n if isinstance(n, bytes) else n.encode())

        lib.objc_msgSend.restype  = ctypes.c_void_p
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        NSApp = lib.objc_msgSend(lib.objc_getClass(b'NSApplication'),
                                 SEL(b'sharedApplication'))

        # Try sendAction:_translate:to:from: — works if an NSTextView is in
        # the responder chain on macOS 12+.
        lib.objc_msgSend.restype  = ctypes.c_bool
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        handled = lib.objc_msgSend(NSApp,
                                   SEL(b'sendAction:to:from:'),
                                   SEL(b'_translate:'),
                                   None, None)
        lib.objc_msgSend.restype  = ctypes.c_void_p
        if handled:
            return
    except Exception:
        pass

    # Fallback: try to open Translate.app directly.
    r = subprocess.run(['open', '-Ra', 'Translate'], capture_output=True)
    if r.returncode == 0:
        # Put text on the general pasteboard so Translate.app can read it.
        proc = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        proc.communicate(text.encode('utf-8'))
        subprocess.Popen(['open', '-a', 'Translate'])
        return

    # Final fallback: open in the default browser.
    import webbrowser
    url = 'https://translate.google.com/?text=' + urllib.parse.quote(text) + '&sl=auto'
    webbrowser.open(url)


def _perform_service(service_name, text):
    """Invoke a named macOS Service with the given text on a private pasteboard."""
    try:
        import ctypes, ctypes.util
        lib = _objc_lib()

        def SEL(n):
            return lib.sel_registerName(n if isinstance(n, bytes) else n.encode())

        def nsstr(s):
            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
            return lib.objc_msgSend(lib.objc_getClass(b'NSString'),
                                    SEL(b'stringWithUTF8String:'), s.encode('utf-8'))

        def msg0(obj, sel):
            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            return lib.objc_msgSend(obj, SEL(sel))

        def msg1(obj, sel, a):
            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            return lib.objc_msgSend(obj, SEL(sel), a)

        def msg2(obj, sel, a, b):
            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                          ctypes.c_void_p, ctypes.c_void_p]
            return lib.objc_msgSend(obj, SEL(sel), a, b)

        pb = msg0(lib.objc_getClass(b'NSPasteboard'), b'pasteboardWithUniqueName')

        # Declare both the modern UTI and the legacy NSStringPboardType so that
        # services like "Look Up in Dictionary" (which only accepts the legacy
        # NSStringPboardType) can read the pasteboard.
        type_uti    = nsstr('public.utf8-plain-text')
        type_legacy = nsstr('NSStringPboardType')
        lib.objc_msgSend.restype  = ctypes.c_void_p
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        alloc = lib.objc_msgSend(lib.objc_getClass(b'NSMutableArray'), SEL(b'alloc'))
        arr   = lib.objc_msgSend(alloc, SEL(b'init'))
        lib.objc_msgSend.restype  = ctypes.c_void_p
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        lib.objc_msgSend(arr, SEL(b'addObject:'), type_uti)
        lib.objc_msgSend(arr, SEL(b'addObject:'), type_legacy)
        msg2(pb, b'declareTypes:owner:', arr, None)
        msg2(pb, b'setString:forType:', nsstr(text), type_uti)
        msg2(pb, b'setString:forType:', nsstr(text), type_legacy)
        lib.objc_msgSend.restype  = ctypes.c_void_p
        lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.objc_msgSend(arr, SEL(b'release'))

        appkit = ctypes.cdll.LoadLibrary(ctypes.util.find_library('AppKit'))
        appkit.NSPerformService.restype  = ctypes.c_bool
        appkit.NSPerformService.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        appkit.NSPerformService(nsstr(service_name), pb)
    except Exception:
        pass


def _build_services_submenu(parent_menu, selected_text):
    """Append the populated macOS Services submenu to parent_menu."""
    try:
        import ctypes, ctypes.util
        lib = _objc_lib()

        def SEL(n):
            return lib.sel_registerName(n if isinstance(n, bytes) else n.encode())

        def py_str(ns):
            if not ns:
                return ''
            lib.objc_msgSend.restype  = ctypes.c_char_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            r = lib.objc_msgSend(ns, SEL(b'UTF8String'))
            lib.objc_msgSend.restype  = ctypes.c_void_p
            return r.decode('utf-8') if r else ''

        def msg0(obj, sel):
            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            return lib.objc_msgSend(obj, SEL(sel))

        def msg_long(obj, sel):
            lib.objc_msgSend.restype  = ctypes.c_long
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            r = lib.objc_msgSend(obj, SEL(sel))
            lib.objc_msgSend.restype  = ctypes.c_void_p
            return r

        def msg_bool(obj, sel):
            lib.objc_msgSend.restype  = ctypes.c_bool
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            r = lib.objc_msgSend(obj, SEL(sel))
            lib.objc_msgSend.restype  = ctypes.c_void_p
            return bool(r)

        def msg_idx(obj, sel, i):
            lib.objc_msgSend.restype  = ctypes.c_void_p
            lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
            return lib.objc_msgSend(obj, SEL(sel), ctypes.c_long(i))

        NSApp    = msg0(lib.objc_getClass(b'NSApplication'), b'sharedApplication')
        svc_menu = msg0(NSApp, b'servicesMenu')
        if not svc_menu or msg_long(svc_menu, b'numberOfItems') == 0:
            return

        parent_menu.addSeparator()
        sub = QMenu("Services", parent_menu)

        def populate(qt_menu, ns_menu):
            for i in range(msg_long(ns_menu, b'numberOfItems')):
                item = msg_idx(ns_menu, b'itemAtIndex:', i)
                if msg_bool(item, b'isSeparatorItem'):
                    qt_menu.addSeparator()
                    continue
                title    = py_str(msg0(item, b'title'))
                submenu  = msg0(item, b'submenu')
                if submenu and msg_long(submenu, b'numberOfItems') > 0:
                    child = QMenu(title, qt_menu)
                    populate(child, submenu)
                    if not child.isEmpty():
                        qt_menu.addMenu(child)
                else:
                    act = qt_menu.addAction(title)
                    act.triggered.connect(
                        lambda checked=False, svc=title, txt=selected_text:
                            _perform_service(svc, txt)
                    )

        populate(sub, svc_menu)
        if not sub.isEmpty():
            parent_menu.addMenu(sub)
    except Exception:
        pass


class ServiceAwareTextEdit(QTextEdit):
    """Read-only QTextEdit with macOS Services (Translate, Look Up, etc.) support.

    On macOS the underlying QNSView is ISA-swizzled at creation time to
    implement NSServicesMenuRequestor, which is required for macOS to
    populate NSApp.servicesMenu() with text services.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Defer swizzle until the native NSView exists (after show)
        QTimer.singleShot(0, lambda: _register_view_for_services(self))

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        selected = self.textCursor().selectedText()
        if selected:
            menu.addSeparator()

            # "Translate" is a built-in NSTextView feature on macOS 12+, not a
            # traditional NSService, so it never appears in the pbs Services
            # menu.  Add it as a direct item instead.
            tr_action = menu.addAction("Translate")
            tr_action.triggered.connect(
                lambda checked=False, t=selected: _open_translation(t)
            )

            # "Look Up in Dictionary" IS a registered service but requires
            # NSStringPboardType.  Expose it directly so it always appears.
            lu_action = menu.addAction("Look Up in Dictionary")
            lu_action.triggered.connect(
                lambda checked=False, t=selected:
                    _perform_service("Look Up in Dictionary", t)
            )

            _build_services_submenu(menu, selected)
        menu.exec(event.globalPos())


def _split_sections(text):
    """Split print_results() output into [(tab_label, body_text), ...] pairs.

    Section headers are delimited by lines of 60 '=' characters. Any text
    before the first header (e.g. warnings) becomes a 'Warnings' tab.
    """
    # re.split with a capturing group interleaves titles with body text:
    # [pre, title1, body1, title2, body2, ...]
    parts = re.split(r'\n={60}\n ([^\n]+)\n={60}', text)
    sections = []

    pre = parts[0].strip('\n')
    if pre.strip():
        sections.append(("Warnings", pre))

    for i in range(1, len(parts), 2):
        raw_title = parts[i].strip()
        body = parts[i + 1].strip('\n') if i + 1 < len(parts) else ""
        # Skip footer sentinels like "END OF ANALYSIS" that have no body
        if not body.strip():
            continue
        label = _TAB_LABELS.get(raw_title, raw_title.title())
        sections.append((label, body))

    return sections


class AnalysisWorker(QThread):
    """Run MIDI analysis in a background thread to keep the UI responsive."""

    finished = pyqtSignal(str)   # emits formatted text output
    error = pyqtSignal(str)      # emits error message

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            results = analyze_midi_file(self.filepath)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                print_results(results)
            self.finished.emit(output.getvalue())
        except Exception as e:
            self.error.emit(str(e))


# ── appearance helpers ────────────────────────────────────────────────────────

def _is_dark_mode(app):
    """Return True when the OS is currently in dark mode.

    On macOS the Qt platform plugin may not have finished initialising when
    this is first called, so styleHints/palette are unreliable at that point.
    Reading the preference directly with 'defaults' is immediate and works on
    all macOS versions regardless of Qt state.
    """
    if sys.platform == "darwin":
        import subprocess
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            return result.stdout.strip().lower() == "dark"
        except Exception:
            pass
    # Non-macOS or 'defaults' unavailable: fall back to Qt APIs
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        pass
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _dark_palette():
    """Return a QPalette suitable for Fusion dark mode."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(53,  53,  53))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Base,            QColor(25,  25,  25))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(53,  53,  53))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(40,  40,  40))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Button,          QColor(53,  53,  53))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.BrightText,      Qt.GlobalColor.red)
    p.setColor(QPalette.ColorRole.Link,            QColor(42,  130, 218))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(42,  130, 218))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(240, 240, 240))
    disabled = QPalette.ColorGroup.Disabled
    p.setColor(disabled, QPalette.ColorRole.WindowText,      QColor(127, 127, 127))
    p.setColor(disabled, QPalette.ColorRole.Text,            QColor(127, 127, 127))
    p.setColor(disabled, QPalette.ColorRole.ButtonText,      QColor(127, 127, 127))
    p.setColor(disabled, QPalette.ColorRole.Highlight,       QColor(80,  80,  80))
    p.setColor(disabled, QPalette.ColorRole.HighlightedText, QColor(127, 127, 127))
    return p


def _apply_appearance(app):
    """Set Fusion style and match palette to the current OS appearance."""
    app.setStyle("Fusion")
    if _is_dark_mode(app):
        app.setPalette(_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())


class MidiApplication(QApplication):
    """QApplication subclass that handles macOS file-open Apple Events.

    When a file is dropped onto the Dock icon or opened via a file
    association, macOS delivers an application:openFiles: Apple Event.
    Qt translates this into a QFileOpenEvent, which must be caught here
    (not in the window) because it can arrive before the window exists.
    """

    def __init__(self, argv):
        super().__init__(argv)
        self._window = None
        self._pending_file = None
        self._current_dark = _is_dark_mode(self)
        _apply_appearance(self)
        # Poll for OS appearance changes every 2 s using the same reliable
        # 'defaults read' method used at startup. Qt's colorSchemeChanged
        # signal does not fire reliably for this purpose.
        self._appearance_timer = QTimer(self)
        self._appearance_timer.timeout.connect(self._poll_appearance)
        self._appearance_timer.start(2000)

    def _poll_appearance(self):
        is_dark = _is_dark_mode(self)
        if is_dark != self._current_dark:
            self._current_dark = is_dark
            _apply_appearance(self)

    def set_window(self, window):
        self._window = window
        if self._pending_file:
            window.analyze(self._pending_file)
            self._pending_file = None

    def event(self, e):
        if isinstance(e, QFileOpenEvent):
            path = e.file()
            if path:
                if self._window:
                    self._window.analyze(path)
                else:
                    self._pending_file = path
            return True
        return super().event(e)


class MidiExaminerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MIDI File Examiner {__version__}")
        self.setMinimumSize(900, 680)
        self.worker = None
        self._file_sections = {}   # path -> [(label, content), ...]
        self._file_order = []      # paths in insertion order
        self._pending_paths = []   # analysis queue
        self._active_worker_path = None

        self._build_menu()
        self._build_ui()
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("File")

        open_action = QAction("Open…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _make_text_view(self):
        """Create a styled read-only monospace text view for a section tab."""
        view = ServiceAwareTextEdit()
        view.setReadOnly(True)
        font = QFont("Menlo")
        if not font.exactMatch():
            font = QFont("Courier New")
        font.setPointSize(11)
        view.setFont(font)
        return view

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # File selection bar
        file_bar = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select a MIDI file or drag one here…")
        self.file_path_edit.setReadOnly(True)
        self.open_button = QPushButton("Open…")
        self.open_button.clicked.connect(self.open_file_dialog)
        file_bar.addWidget(self.file_path_edit)
        file_bar.addWidget(self.open_button)
        layout.addLayout(file_bar)

        # Horizontal splitter: sidebar (file list) on the left, tabs on the right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.sidebar = QListWidget()
        self.sidebar.setMinimumWidth(80)
        self.sidebar.setMaximumWidth(320)
        self.sidebar.currentItemChanged.connect(self._on_sidebar_selection_changed)
        splitter.addWidget(self.sidebar)

        self.tab_widget = QTabWidget()
        self.tab_widget.setUsesScrollButtons(True)
        splitter.addWidget(self.tab_widget)

        splitter.setSizes([180, 720])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.statusBar().showMessage("Ready — open a MIDI file to begin.")

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------

    def open_file_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open MIDI File(s)",
            "",
            "MIDI Files (*.mid *.midi);;All Files (*)",
        )
        for path in paths:
            self.analyze(path)

    def analyze(self, path):
        # Already in the sidebar (analyzed or queued) — just select it.
        if path in self._file_sections or path in self._pending_paths \
                or path == self._active_worker_path:
            self._select_sidebar_item(path)
            return

        self._file_order.append(path)
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.ItemDataRole.UserRole, path)
        self.sidebar.addItem(item)
        self.sidebar.setCurrentItem(item)

        self._pending_paths.append(path)
        self._start_next_worker()

    def _start_next_worker(self):
        if self._active_worker_path is not None or not self._pending_paths:
            return
        path = self._pending_paths.pop(0)
        self._active_worker_path = path
        self.statusBar().showMessage(f"Analyzing: {os.path.basename(path)}")
        self.worker = AnalysisWorker(path)
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_done(self, text):
        path = self._active_worker_path
        self._file_sections[path] = _split_sections(text)
        self._active_worker_path = None
        # Populate tabs if this file is currently selected in the sidebar
        current = self.sidebar.currentItem()
        if current and current.data(Qt.ItemDataRole.UserRole) == path:
            self._populate_tabs(path)
        self.statusBar().showMessage(f"Analysis complete: {os.path.basename(path)}")
        self._start_next_worker()

    def _on_analysis_error(self, message):
        path = self._active_worker_path
        self._file_sections[path] = [("Error", f"Error: {message}")]
        self._active_worker_path = None
        current = self.sidebar.currentItem()
        if current and current.data(Qt.ItemDataRole.UserRole) == path:
            self._populate_tabs(path)
        self.statusBar().showMessage(f"Error: {os.path.basename(path)}")
        self._start_next_worker()

    def _populate_tabs(self, path):
        self.tab_widget.clear()
        for label, content in self._file_sections.get(path, []):
            view = self._make_text_view()
            view.setPlainText(content)
            view.moveCursor(view.textCursor().MoveOperation.Start)
            idx = self.tab_widget.addTab(view, label)
            if re.match(r'^\s*\(No .+ found\)\s*$', content):
                self.tab_widget.setTabEnabled(idx, False)

    def _select_sidebar_item(self, path):
        for i in range(self.sidebar.count()):
            item = self.sidebar.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self.sidebar.setCurrentItem(item)
                return

    def _on_sidebar_selection_changed(self, current, previous):
        if current is None:
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        self.file_path_edit.setText(path)
        if path in self._file_sections:
            self._populate_tabs(path)
        else:
            # Still analyzing — clear tabs and wait for _on_analysis_done
            self.tab_widget.clear()

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            if any(u.toLocalFile().lower().endswith((".mid", ".midi"))
                   for u in event.mimeData().urls()):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".mid", ".midi")):
                self.analyze(path)


def main():
    app = MidiApplication(sys.argv)
    app.setApplicationName("MIDI File Examiner")
    app.setApplicationVersion(__version__)

    # On macOS, set up the Services menu so pbs can populate it with text
    # services (Translate, Look Up, etc.).  Qt never does this itself.
    if sys.platform == 'darwin':
        _setup_services_menu()

    window = MidiExaminerWindow()
    app.set_window(window)
    window.show()

    # If file paths were passed as command-line arguments, open them immediately.
    for arg in sys.argv[1:]:
        if arg.lower().endswith((".mid", ".midi")):
            window.analyze(arg)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
