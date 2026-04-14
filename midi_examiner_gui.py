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
from collections import deque

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget,
        QVBoxLayout, QHBoxLayout, QFormLayout,
        QPushButton, QCheckBox, QGroupBox, QLabel, QLineEdit,
        QTextEdit, QFileDialog, QTabWidget, QMenu,
        QListWidget, QListWidgetItem, QSplitter,
        QDialog, QDialogButtonBox, QScrollArea,
        QSpinBox, QDoubleSpinBox, QComboBox, QProgressBar,
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

from midi_examiner import (
    __version__, analyze_midi_file, print_results, collect_midi_files,
    _filter_summary, _matches_advanced_filters, _midi_note_name,
    _TIME_SIG_VALID_DENOMS, _KEY_SIGNATURES, _key_display_name,
)

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
    # Guard: a null base_class would cause objc_allocateClassPair to crash.
    if not base_class:
        return None
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

        ns_view = int(widget.viewport().winId())
        # Guard: winId() can return 0 if the native window hasn't been created
        # yet or the widget is in a partially-initialised state.  Passing 0 to
        # object_getClass / objc_allocateClassPair causes an immediate crash.
        if not ns_view:
            return
        base_class = lib.object_getClass(ns_view)
        # Guard: object_getClass can return NULL for non-ObjC objects.
        if not base_class:
            return
        new_cls = _make_services_class(lib, base_class)
        if not new_cls:
            return
        lib.object_setClass(ns_view, new_cls)
        _svc_view_map[ns_view] = _weakref.ref(widget)
        # Remove the stale entry when the widget is destroyed so that the
        # freed NSView pointer cannot linger as a dangling key in _svc_view_map.
        # A dangling pointer in the map risks a crash if macOS calls our
        # swizzled ObjC method on memory that has since been reallocated.
        _ns = ns_view  # capture by value for the closure
        widget.destroyed.connect(lambda _obj=None, _k=_ns: _svc_view_map.pop(_k, None))
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
        self._services_registered = False

    def showEvent(self, event):
        """Register for macOS Services on first show, when the native NSView exists."""
        super().showEvent(event)
        if not self._services_registered:
            self._services_registered = True
            _register_view_for_services(self)

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


# Background/foreground colours for each detected MIDI standard.
# Colours chosen to reflect brand identity; text colour maximises WCAG contrast.
_STANDARD_STYLES = {
    "GM":  {"bg": QColor("#228B22"), "fg": QColor("#000000")},  # forest green / black
    "GM2": {"bg": QColor("#3DAA3D"), "fg": QColor("#000000")},  # lighter forest green / black
    "GS":  {"bg": QColor("#F26522"), "fg": QColor("#000000")},  # Roland orange / black
    "XG":  {"bg": QColor("#492786"), "fg": QColor("#FFFFFF")},  # Yamaha purple / white
}


# Standard filter checkboxes: (internal key, display label).
# Multiple checked entries use OR logic — show files matching any checked standard.
# Keys match the CLI --filter tag names.
_STANDARD_FILTER_DEFS = [
    ("GM",      "GM"),
    ("GM2",     "GM2"),
    ("GS",      "GS"),
    ("XG",      "XG"),
    ("unknown", "Unknown"),
]

# Modifier filter checkboxes: (internal key, display label, tooltip).
# Tri-state: checked = show only files with this tag; partially checked (–) = hide those files.
# Keys match the CLI --filter / --exclude tag names.
_MODIFIER_FILTER_DEFS = [
    ("assumed",  "[?]",
     "Checked: show only files with an assumed standard\nPartially checked (\u2013): hide files with an assumed standard"),
    ("warnings", "[!]",
     "Checked: show only files with warnings\nPartially checked (\u2013): hide files with warnings"),
    ("KAR",      "KAR",
     "Checked: show only Soft Karaoke files\nPartially checked (\u2013): hide Soft Karaoke files"),
]


def _apply_standard_style(item, standard, has_warnings=False, assumed=False, is_karaoke=False):
    """Apply background/foreground colour and append tag(s) to item text.

    Tags appended (in order): [GM/GM2/GS/XG] [KAR] [?] [!]
      [KAR] file is Soft Karaoke format
      [?]   standard was assumed from bank/program messages, not from SysEx
      [!]   file has one or more warnings
    """
    style = _STANDARD_STYLES.get(standard)
    if style:
        item.setBackground(style["bg"])
        item.setForeground(style["fg"])
    path = item.data(Qt.ItemDataRole.UserRole)
    tags = []
    if standard:
        tags.append(f"[{standard}]")
    if is_karaoke:
        tags.append("[KAR]")
    if assumed:
        tags.append("[?]")
    if has_warnings:
        tags.append("[!]")
    suffix = ("  " + " ".join(tags)) if tags else ""
    # Use the stored base label (set at item creation) so the depth-indentation
    # prefix is preserved regardless of how many times this function is called.
    base = item.data(Qt.ItemDataRole.UserRole.value + 1) \
        or os.path.basename(item.data(Qt.ItemDataRole.UserRole))
    item.setText(f"{base}{suffix}")


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

    # emits (formatted text, detected_standard or "", has_warnings, standard_assumed,
    #        is_karaoke, filter_summary_dict)
    finished = pyqtSignal(str, str, bool, bool, bool, object)
    error = pyqtSignal(str)

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            results = analyze_midi_file(self.filepath)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                print_results(results)
            standard    = results.get("detected_standard") or ""
            has_warnings = bool(results.get("warnings"))
            assumed     = bool(results.get("standard_assumed"))
            is_karaoke  = bool(results.get("karaoke"))
            fsum        = _filter_summary(results)
            self.finished.emit(output.getvalue(), standard, has_warnings, assumed,
                               is_karaoke, fsum)
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


def _hrow(*widgets):
    """Return a QWidget that lays out *widgets* horizontally with tight margins."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(4)
    for widget in widgets:
        h.addWidget(widget)
    h.addStretch()
    return w


class _DenomSpinBox(QSpinBox):
    """QSpinBox for MIDI time signature denominators.

    Arrow keys and the scroll wheel step through the valid values only
    (0 = no constraint, then 1, 2, 4, 8, 16, 32, 64, 128).  Free-text
    entry is accepted; get_filters() ignores the value if it is not a
    valid power of 2.
    """

    _STEPS = [0, 1, 2, 4, 8, 16, 32, 64, 128]

    def stepBy(self, steps):
        cur = self.value()
        vals = self._STEPS
        try:
            idx = vals.index(cur)
        except ValueError:
            # Snap to the nearest step before moving.
            idx = min(range(len(vals)), key=lambda i: abs(vals[i] - cur))
        self.setValue(vals[max(0, min(len(vals) - 1, idx + steps))])


class AdvancedFilterDialog(QDialog):
    """Modal dialog for configuring advanced MIDI file filter conditions.

    Presents filter controls in four sections:
        File Info         – duration, MIDI format type, track count
        Notes & Velocity  – note range, velocity range, peak polyphony, key signature
        Timing & Events   – timing type, time signature, tempo range, CC numbers, aftertouch
        Search            – text search, SysEx hex pattern

    Fields use a sentinel value (—) to indicate "no constraint".  Only fields
    with a non-sentinel value contribute to the returned filter dict.

    Call get_filters() after exec() returns QDialog.Accepted.
    """

    def __init__(self, current_filters, *, gs_active=False, xg_active=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._gs_active = gs_active
        self._xg_active = xg_active
        self._build_ui()
        self._load_filters(current_filters or {})

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        small_font = self.font()
        small_font.setPointSize(max(8, small_font.pointSize() - 1))

        # ── File Info ─────────────────────────────────────────────────────────
        fi_grp  = QGroupBox("File Info")
        fi_form = QFormLayout(fi_grp)
        fi_form.setSpacing(4)
        fi_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._dur_min = QDoubleSpinBox()
        self._dur_min.setRange(0.0, 86400.0)
        self._dur_min.setDecimals(1)
        self._dur_min.setSuffix(" s")
        self._dur_min.setSpecialValueText("—")
        self._dur_min.setToolTip("Minimum duration in seconds (— = no limit)")

        self._dur_max = QDoubleSpinBox()
        self._dur_max.setRange(0.0, 86400.0)
        self._dur_max.setDecimals(1)
        self._dur_max.setSuffix(" s")
        self._dur_max.setSpecialValueText("—")
        self._dur_max.setToolTip("Maximum duration in seconds (— = no limit)")

        fi_form.addRow("Duration:",
                       _hrow(QLabel("min"), self._dur_min, QLabel("max"), self._dur_max))

        fmt_row = QWidget()
        fmt_hbox = QHBoxLayout(fmt_row)
        fmt_hbox.setContentsMargins(0, 0, 0, 0)
        fmt_hbox.setSpacing(8)
        self._fmt_checks = {}
        for i in range(3):
            cb = QCheckBox(f"Type {i}")
            cb.setFont(small_font)
            cb.setToolTip(f"Include only MIDI format type {i} files")
            self._fmt_checks[i] = cb
            fmt_hbox.addWidget(cb)
        fmt_hbox.addStretch()
        fi_form.addRow("Format:", fmt_row)

        self._trk_min = QSpinBox()
        self._trk_min.setRange(-1, 9999)
        self._trk_min.setSpecialValueText("—")
        self._trk_min.setToolTip("Minimum track count (— = no limit)")

        self._trk_max = QSpinBox()
        self._trk_max.setRange(-1, 9999)
        self._trk_max.setSpecialValueText("—")
        self._trk_max.setToolTip("Maximum track count (— = no limit)")

        fi_form.addRow("Tracks:",
                       _hrow(QLabel("min"), self._trk_min, QLabel("max"), self._trk_max))

        # Roland SC minimum version (OR logic — any checked generation matches)
        sc_row = QWidget()
        sc_hbox = QHBoxLayout(sc_row)
        sc_hbox.setContentsMargins(0, 0, 0, 0)
        sc_hbox.setSpacing(6)
        self._sc_checks = {}
        for gen, label in [(1, "SC-55"), (2, "SC-88"), (3, "SC-88Pro"), (4, "SC-8850")]:
            cb = QCheckBox(label)
            cb.setFont(small_font)
            cb.setToolTip(
                f"Show GS files whose minimum required Sound Canvas is the {label}")
            self._sc_checks[gen] = cb
            sc_hbox.addWidget(cb)
        sc_hbox.addStretch()
        fi_form.addRow("Roland SC req.:", sc_row)

        # Yamaha XG minimum level (OR logic — any checked level matches)
        xg_row = QWidget()
        xg_hbox = QHBoxLayout(xg_row)
        xg_hbox.setContentsMargins(0, 0, 0, 0)
        xg_hbox.setSpacing(6)
        self._xg_checks = {}
        for lvl, label, device in [
            (1, "Level 1", "MU50/MU80/MU90"),
            (2, "Level 2", "MU100"),
            (3, "Level 3", "MU128"),
        ]:
            cb = QCheckBox(label)
            cb.setFont(small_font)
            cb.setToolTip(
                f"Show XG files whose minimum required device is {device} (XG {label})")
            self._xg_checks[lvl] = cb
            xg_hbox.addWidget(cb)
        xg_hbox.addStretch()
        fi_form.addRow("Yamaha XG level:", xg_row)

        vbox.addWidget(fi_grp)

        # ── Notes & Velocity ──────────────────────────────────────────────────
        note_grp  = QGroupBox("Notes && Velocity")
        note_form = QFormLayout(note_grp)
        note_form.setSpacing(4)
        note_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._note_min = QSpinBox()
        self._note_min.setRange(-1, 127)
        self._note_min.setSpecialValueText("—")
        self._note_min.setToolTip(
            "File's lowest note must be \u2265 this value (— = no limit)\n"
            "MIDI 0 (C\u22121) to 127 (G9); file doesn't go below this note")

        self._note_min_lbl = QLabel("")
        self._note_min_lbl.setFont(small_font)
        self._note_min_lbl.setMinimumWidth(30)
        self._note_min.valueChanged.connect(self._refresh_note_labels)

        self._note_max = QSpinBox()
        self._note_max.setRange(-1, 127)
        self._note_max.setSpecialValueText("—")
        self._note_max.setToolTip(
            "File's highest note must be \u2264 this value (— = no limit)\n"
            "File doesn't go above this note")

        self._note_max_lbl = QLabel("")
        self._note_max_lbl.setFont(small_font)
        self._note_max_lbl.setMinimumWidth(30)
        self._note_max.valueChanged.connect(self._refresh_note_labels)

        note_form.addRow("Note range:",
                         _hrow(QLabel("min"), self._note_min, self._note_min_lbl,
                               QLabel("max"), self._note_max, self._note_max_lbl))

        self._vel_min = QSpinBox()
        self._vel_min.setRange(-1, 127)
        self._vel_min.setSpecialValueText("—")
        self._vel_min.setToolTip(
            "File's lowest velocity must be \u2265 this value (— = no limit)")

        self._vel_max = QSpinBox()
        self._vel_max.setRange(-1, 127)
        self._vel_max.setSpecialValueText("—")
        self._vel_max.setToolTip(
            "File's highest velocity must be \u2264 this value (— = no limit)")

        note_form.addRow("Velocity:",
                         _hrow(QLabel("min"), self._vel_min, QLabel("max"), self._vel_max))

        self._poly_min = QSpinBox()
        self._poly_min.setRange(-1, 9999)
        self._poly_min.setSpecialValueText("—")
        self._poly_min.setToolTip(
            "File's global peak polyphony must be \u2265 this value (— = no limit)")

        self._poly_max = QSpinBox()
        self._poly_max.setRange(-1, 9999)
        self._poly_max.setSpecialValueText("—")
        self._poly_max.setToolTip(
            "File's global peak polyphony must be \u2264 this value (— = no limit)")

        note_form.addRow("Peak polyphony:",
                         _hrow(QLabel("min"), self._poly_min, QLabel("max"), self._poly_max))

        self._key_sig_list = QListWidget()
        self._key_sig_list.setSelectionMode(
            QListWidget.SelectionMode.NoSelection)
        self._key_sig_list.setToolTip(
            "Check one or more key signatures to show only files that match "
            "(OR logic). Leave all unchecked for no constraint.")
        self._key_sig_list.setMaximumHeight(112)  # ~5 rows visible; rest scrollable
        for ks in _KEY_SIGNATURES:
            item = QListWidgetItem(_key_display_name(ks))
            item.setData(Qt.ItemDataRole.UserRole, ks)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._key_sig_list.addItem(item)
        note_form.addRow("Key signature:", self._key_sig_list)

        vbox.addWidget(note_grp)

        # ── Timing & Events ───────────────────────────────────────────────────
        evt_grp  = QGroupBox("Timing && Events")
        evt_form = QFormLayout(evt_grp)
        evt_form.setSpacing(4)
        evt_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Timing type pop-up (Any / PPQ / SMPTE).
        self._timing_type_combo = QComboBox()
        self._timing_type_combo.addItems(
            ["Any", "PPQ — tempo-based timing", "SMPTE — frame-based timing"])
        self._timing_type_combo.setToolTip("Filter by MIDI timing type")
        evt_form.addRow("Timing type:", self._timing_type_combo)

        # Time signature: two spinboxes with a "/" label between them.
        self._timesig_num = QSpinBox()
        self._timesig_num.setRange(0, 255)
        self._timesig_num.setSpecialValueText("—")
        self._timesig_num.setToolTip("Numerator (1\u2013255; — = no constraint)")
        self._timesig_num.setMaximumWidth(54)

        self._timesig_denom = _DenomSpinBox()
        self._timesig_denom.setRange(0, 128)
        self._timesig_denom.setSpecialValueText("—")
        self._timesig_denom.setToolTip(
            "Denominator — must be a power of 2 (1, 2, 4, 8, 16, 32, 64, 128)\n"
            "Arrow keys step through valid values only; — = no constraint")
        self._timesig_denom.setMaximumWidth(54)

        evt_form.addRow("Time signature:",
                        _hrow(self._timesig_num, QLabel("/"), self._timesig_denom))

        self._tempo_min = QDoubleSpinBox()
        self._tempo_min.setRange(0.0, 9999.0)
        self._tempo_min.setDecimals(1)
        self._tempo_min.setSuffix(" BPM")
        self._tempo_min.setSpecialValueText("—")
        self._tempo_min.setToolTip(
            "File's tempo range must reach at least this BPM (— = no limit)")

        self._tempo_max = QDoubleSpinBox()
        self._tempo_max.setRange(0.0, 9999.0)
        self._tempo_max.setDecimals(1)
        self._tempo_max.setSuffix(" BPM")
        self._tempo_max.setSpecialValueText("—")
        self._tempo_max.setToolTip(
            "File's tempo range must include at most this BPM (— = no limit)")

        evt_form.addRow("Tempo:",
                        _hrow(QLabel("min"), self._tempo_min, QLabel("max"), self._tempo_max))

        self._cc_edit = QLineEdit()
        self._cc_edit.setPlaceholderText("e.g. 7, 10, 64")
        self._cc_edit.setToolTip(
            "Comma-separated CC numbers (0-127)\n"
            "File must use ALL listed CCs (AND logic)")
        evt_form.addRow("CC numbers:", self._cc_edit)

        self._poly_at_combo = QComboBox()
        self._poly_at_combo.addItems(
            ["Any", "Yes — file uses poly AT", "No — file has no poly AT"])
        self._poly_at_combo.setToolTip("Filter by polyphonic (per-note) aftertouch usage")
        evt_form.addRow("Poly aftertouch:", self._poly_at_combo)

        self._ch_at_combo = QComboBox()
        self._ch_at_combo.addItems(
            ["Any", "Yes — file uses channel AT", "No — file has no channel AT"])
        self._ch_at_combo.setToolTip("Filter by channel aftertouch usage")
        evt_form.addRow("Channel aftertouch:", self._ch_at_combo)

        vbox.addWidget(evt_grp)

        # ── Search ────────────────────────────────────────────────────────────
        search_grp  = QGroupBox("Search")
        search_form = QFormLayout(search_grp)
        search_form.setSpacing(4)
        search_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._text_search = QLineEdit()
        self._text_search.setPlaceholderText(
            "Substring in text events, track names, metadata…")
        self._text_search.setToolTip("Case-insensitive substring search across all text")
        search_form.addRow("Text:", self._text_search)

        self._sysex_search = QLineEdit()
        self._sysex_search.setPlaceholderText("e.g. 41 10 42  (hex bytes, spaces optional)")
        self._sysex_search.setToolTip(
            "Hex byte sequence that must appear in at least one SysEx message\n"
            "Spaces are ignored: '411042' and '41 10 42' are equivalent")
        search_form.addRow("SysEx pattern:", self._sysex_search)

        vbox.addWidget(search_grp)
        vbox.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        # Button row
        btn_row = QHBoxLayout()
        clear_btn = QPushButton("Reset")
        clear_btn.setToolTip("Reset all fields to no constraint")
        clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        std_btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        std_btns.accepted.connect(self.accept)
        std_btns.rejected.connect(self.reject)
        btn_row.addWidget(std_btns)
        outer.addLayout(btn_row)

    # ── State load / save ─────────────────────────────────────────────────────

    def _load_filters(self, f):
        """Populate UI widgets from filter dict *f*."""
        self._dur_min.setValue(f.get('min_duration', 0.0))
        self._dur_max.setValue(f.get('max_duration', 0.0))
        fmts = f.get('formats', set())
        for i, cb in self._fmt_checks.items():
            cb.setChecked(i in fmts)
        self._trk_min.setValue(f.get('min_tracks', -1))
        self._trk_max.setValue(f.get('max_tracks', -1))
        self._note_min.setValue(f.get('min_note', -1))
        self._note_max.setValue(f.get('max_note', -1))
        self._refresh_note_labels()
        self._vel_min.setValue(f.get('min_velocity', -1))
        self._vel_max.setValue(f.get('max_velocity', -1))
        self._poly_min.setValue(f.get('min_polyphony', -1))
        self._poly_max.setValue(f.get('max_polyphony', -1))
        ks_active = f.get('key_signatures', set())
        for i in range(self._key_sig_list.count()):
            item = self._key_sig_list.item(i)
            item.setCheckState(
                Qt.CheckState.Checked
                if item.data(Qt.ItemDataRole.UserRole) in ks_active
                else Qt.CheckState.Unchecked
            )
        tt = f.get('timing_type')
        self._timing_type_combo.setCurrentIndex(
            0 if tt is None else (1 if tt == 'PPQ' else 2))
        ts = f.get('time_signature')
        self._timesig_num.setValue(ts[0] if ts else 0)
        self._timesig_denom.setValue(ts[1] if ts else 0)
        self._tempo_min.setValue(f.get('min_tempo', 0.0))
        self._tempo_max.setValue(f.get('max_tempo', 0.0))
        cc_nums = f.get('cc_numbers', set())
        self._cc_edit.setText(
            ', '.join(str(c) for c in sorted(cc_nums)) if cc_nums else '')
        pat = f.get('poly_aftertouch')
        self._poly_at_combo.setCurrentIndex(
            0 if pat is None else (1 if pat else 2))
        cat = f.get('channel_aftertouch')
        self._ch_at_combo.setCurrentIndex(
            0 if cat is None else (1 if cat else 2))
        self._text_search.setText(f.get('search_text', ''))
        self._sysex_search.setText(f.get('sysex_pattern', ''))
        # When the key is absent (never modified), default to all checked only if
        # the corresponding standard is active in the main filter; otherwise default
        # to none checked so unrelated sub-options don't appear pre-selected.
        all_sc = set(self._sc_checks)
        sc_default = all_sc if self._gs_active else set()
        sc_versions = f.get('sc_versions', sc_default)
        for gen, cb in self._sc_checks.items():
            cb.setChecked(gen in sc_versions)
        all_xg = set(self._xg_checks)
        xg_default = all_xg if self._xg_active else set()
        xg_levels = f.get('xg_levels', xg_default)
        for lvl, cb in self._xg_checks.items():
            cb.setChecked(lvl in xg_levels)

    def get_filters(self):
        """Return the current filter state as a dict for _matches_advanced_filters."""
        adv = {}

        v = self._dur_min.value()
        if v > 0.0:
            adv['min_duration'] = v
        v = self._dur_max.value()
        if v > 0.0:
            adv['max_duration'] = v

        fmts = {i for i, cb in self._fmt_checks.items() if cb.isChecked()}
        if fmts:
            adv['formats'] = fmts

        v = self._trk_min.value()
        if v >= 0:
            adv['min_tracks'] = v
        v = self._trk_max.value()
        if v >= 0:
            adv['max_tracks'] = v

        v = self._note_min.value()
        if v >= 0:
            adv['min_note'] = v
        v = self._note_max.value()
        if v >= 0:
            adv['max_note'] = v

        v = self._vel_min.value()
        if v >= 0:
            adv['min_velocity'] = v
        v = self._vel_max.value()
        if v >= 0:
            adv['max_velocity'] = v

        v = self._poly_min.value()
        if v >= 0:
            adv['min_polyphony'] = v
        v = self._poly_max.value()
        if v >= 0:
            adv['max_polyphony'] = v

        ks_sel = {
            self._key_sig_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._key_sig_list.count())
            if self._key_sig_list.item(i).checkState() == Qt.CheckState.Checked
        }
        if ks_sel:
            adv['key_signatures'] = ks_sel

        tt_idx = self._timing_type_combo.currentIndex()
        if tt_idx == 1:
            adv['timing_type'] = 'PPQ'
        elif tt_idx == 2:
            adv['timing_type'] = 'SMPTE'

        ts_num   = self._timesig_num.value()
        ts_denom = self._timesig_denom.value()
        if ts_num > 0 and ts_denom in _TIME_SIG_VALID_DENOMS:
            adv['time_signature'] = (ts_num, ts_denom)

        v = self._tempo_min.value()
        if v > 0.0:
            adv['min_tempo'] = v
        v = self._tempo_max.value()
        if v > 0.0:
            adv['max_tempo'] = v

        cc_text = self._cc_edit.text().strip()
        if cc_text:
            cc_nums = set()
            for tok in cc_text.replace(',', ' ').split():
                try:
                    n = int(tok)
                    if 0 <= n <= 127:
                        cc_nums.add(n)
                except ValueError:
                    pass
            if cc_nums:
                adv['cc_numbers'] = cc_nums

        idx = self._poly_at_combo.currentIndex()
        if idx == 1:
            adv['poly_aftertouch'] = True
        elif idx == 2:
            adv['poly_aftertouch'] = False

        idx = self._ch_at_combo.currentIndex()
        if idx == 1:
            adv['channel_aftertouch'] = True
        elif idx == 2:
            adv['channel_aftertouch'] = False

        t = self._text_search.text().strip()
        if t:
            adv['search_text'] = t
        s = self._sysex_search.text().strip()
        if s:
            adv['sysex_pattern'] = s

        # Only store sc_versions/xg_levels when the selection is a strict subset
        # (all options checked = no constraint, same as none checked).
        sc_versions = {gen for gen, cb in self._sc_checks.items() if cb.isChecked()}
        if sc_versions and sc_versions != set(self._sc_checks):
            adv['sc_versions'] = sc_versions
        xg_levels = {lvl for lvl, cb in self._xg_checks.items() if cb.isChecked()}
        if xg_levels and xg_levels != set(self._xg_checks):
            adv['xg_levels'] = xg_levels

        return adv

    def _clear_all(self):
        """Reset all filter fields to the no-constraint state."""
        self._dur_min.setValue(0.0)
        self._dur_max.setValue(0.0)
        for cb in self._fmt_checks.values():
            cb.setChecked(False)
        self._trk_min.setValue(-1)
        self._trk_max.setValue(-1)
        self._note_min.setValue(-1)
        self._note_max.setValue(-1)
        self._vel_min.setValue(-1)
        self._vel_max.setValue(-1)
        self._poly_min.setValue(-1)
        self._poly_max.setValue(-1)
        for i in range(self._key_sig_list.count()):
            self._key_sig_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self._timing_type_combo.setCurrentIndex(0)
        self._timesig_num.setValue(0)
        self._timesig_denom.setValue(0)
        self._tempo_min.setValue(0.0)
        self._tempo_max.setValue(0.0)
        self._cc_edit.clear()
        self._poly_at_combo.setCurrentIndex(0)
        self._ch_at_combo.setCurrentIndex(0)
        self._text_search.clear()
        self._sysex_search.clear()
        # Reset to all-checked (no constraint) when the standard is active;
        # otherwise reset to none-checked so unrelated options stay clear.
        for cb in self._sc_checks.values():
            cb.setChecked(self._gs_active)
        for cb in self._xg_checks.values():
            cb.setChecked(self._xg_active)

    def _refresh_note_labels(self):
        """Update the note-name labels next to the note range spinboxes."""
        v = self._note_min.value()
        self._note_min_lbl.setText(_midi_note_name(v) if v >= 0 else "")
        v = self._note_max.value()
        self._note_max_lbl.setText(_midi_note_name(v) if v >= 0 else "")


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
            window.analyze(self._pending_file, sorted_insert=True)
            self._pending_file = None

    def event(self, e):
        if isinstance(e, QFileOpenEvent):
            path = e.file()
            if path:
                if self._window:
                    self._window.analyze(path, sorted_insert=True)
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
        self._pending_paths = deque()  # analysis queue (FIFO)
        self._pending_set = set()      # O(1) membership test for _pending_paths
        self._sidebar_items = {}   # path -> QListWidgetItem (O(1) lookup)
        self._file_tags = {}           # path -> {standard, has_warnings, assumed, is_karaoke, ...}
        self._advanced_filters = {}    # advanced filter state (see AdvancedFilterDialog)
        self._folder_count = 0         # number of folder-header rows in the sidebar
        self._visible_count = 0    # number of visible (non-hidden) file items
        self._active_worker_path = None
        # Keeps the last 2 retired AnalysisWorker Python wrappers alive after
        # self.worker is reassigned.  Without this, Python GC deletes the
        # wrapper immediately when self.worker = new_worker executes, which
        # calls QThread::~QThread() while the thread is still in
        # sip_api_end_thread() waiting for the GIL — an instant hard abort.
        # By the time an entry is pushed out of this deque (when the NEXT
        # worker finishes), the earlier thread has long since truly exited.
        self._retired_workers = deque(maxlen=2)
        self._total_files = 0      # files added in the current batch
        self._completed_files = 0  # files finished (done or error) in current batch

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

        open_folder_action = QAction("Open Folder…", self)
        open_folder_action.triggered.connect(self.open_folder_dialog)
        file_menu.addAction(open_folder_action)

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
        self.open_folder_button = QPushButton("Open Folder…")
        self.open_folder_button.clicked.connect(self.open_folder_dialog)
        file_bar.addWidget(self.file_path_edit)
        file_bar.addWidget(self.open_button)
        file_bar.addWidget(self.open_folder_button)
        layout.addLayout(file_bar)

        # Horizontal splitter: sidebar (file list) on the left, tabs on the right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(4)

        # Filter controls — shown above the file list.
        # Standard checkboxes use OR logic: checking GM and GS shows files matching either.
        # Modifier checkboxes are tri-state: checked = show only, partially checked (–) = hide.
        filter_group = QGroupBox("Filter")
        filter_font = filter_group.font()
        filter_font.setPointSize(max(8, filter_font.pointSize() - 1))
        filter_group.setFont(filter_font)
        filter_vlayout = QVBoxLayout(filter_group)
        filter_vlayout.setContentsMargins(4, 4, 4, 4)
        filter_vlayout.setSpacing(3)

        # Standard filter row: check any combination to show matching files (OR logic).
        standard_row = QHBoxLayout()
        standard_row.setSpacing(4)
        self._standard_checks = {}   # key -> QCheckBox
        for key, label in _STANDARD_FILTER_DEFS:
            cb = QCheckBox(label)
            cb.setFont(filter_font)
            cb.setToolTip("Check to include files matching this MIDI standard (OR logic)")
            cb.stateChanged.connect(self._on_filter_changed)
            self._standard_checks[key] = cb
            standard_row.addWidget(cb)
        # When GS or XG is unchecked, clear the corresponding advanced filter
        # entries so the two filter panels stay consistent.
        self._standard_checks['GS'].stateChanged.connect(self._on_gs_check_changed)
        self._standard_checks['XG'].stateChanged.connect(self._on_xg_check_changed)
        standard_row.addStretch()
        filter_vlayout.addLayout(standard_row)

        # Modifier filter row: tri-state checkboxes (checked = show only, – = hide).
        modifier_row = QHBoxLayout()
        modifier_row.setSpacing(4)
        self._modifier_checks = {}   # key -> QCheckBox (tri-state)
        for key, label, tip in _MODIFIER_FILTER_DEFS:
            cb = QCheckBox(label)
            cb.setFont(filter_font)
            cb.setTristate(True)
            cb.setToolTip(tip)
            cb.stateChanged.connect(self._on_filter_changed)
            cb.clicked.connect(self._make_modifier_cycle_handler(cb))
            self._modifier_checks[key] = cb
            modifier_row.addWidget(cb)
        modifier_row.addStretch()
        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setFont(filter_font)
        self._reset_btn.setToolTip("Clear all standard, modifier, and advanced filters")
        self._reset_btn.clicked.connect(self._reset_all_filters)
        modifier_row.addWidget(self._reset_btn)
        self._adv_btn = QPushButton("Advanced\u2026")
        self._adv_btn.setFont(filter_font)
        self._adv_btn.setToolTip(
            "Open the Advanced Filter dialog to filter by duration, note range, "
            "velocity, tempo, CC usage, text, SysEx, and more")
        self._adv_btn.clicked.connect(self._open_advanced_filter)
        modifier_row.addWidget(self._adv_btn)
        filter_vlayout.addLayout(modifier_row)
        sidebar_layout.addWidget(filter_group)

        # Debounce timer: coalesces rapid checkbox toggles so that at most one
        # full O(n) filter scan runs per 100 ms burst of changes.
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(100)
        self._filter_timer.timeout.connect(self._apply_sidebar_filter)

        self.sidebar = QListWidget()
        self.sidebar.setMinimumWidth(80)
        self.sidebar.setMaximumWidth(320)
        self.sidebar.currentItemChanged.connect(self._on_sidebar_selection_changed)
        sidebar_layout.addWidget(self.sidebar)

        self.sidebar_status_label = QLabel("")
        self.sidebar_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.sidebar_status_label.font()
        font.setPointSize(font.pointSize() - 1)
        self.sidebar_status_label.setFont(font)
        sidebar_layout.addWidget(self.sidebar_status_label)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self._clear_files)
        sidebar_layout.addWidget(self.clear_button)

        splitter.addWidget(sidebar_widget)

        self.tab_widget = QTabWidget()
        self.tab_widget.setUsesScrollButtons(True)
        splitter.addWidget(self.tab_widget)

        splitter.setSizes([180, 720])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.statusBar().showMessage("Ready — open a MIDI file to begin.")
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(180)
        self._progress_bar.setFixedHeight(16)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%v / %m")
        self._progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self._progress_bar)

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
            self.analyze(path, sorted_insert=True)

    def open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Open Folder",
            "",
        )
        if folder:
            self._open_paths([folder])

    def _open_paths(self, paths):
        """Expand a list of file/directory paths and queue each MIDI file for analysis.

        Directories are scanned recursively up to 6 levels deep.  If any files
        were excluded due to the depth limit a warning dialog is shown.
        Directory scans show folder-name headers in the sidebar to mirror the
        filesystem hierarchy.
        """
        from PyQt6.QtWidgets import QMessageBox
        # Opening a folder replaces the current list rather than appending to it.
        if any(os.path.isdir(p) for p in paths):
            self._clear_files()
        all_warnings = []
        for path in paths:
            if os.path.isdir(path):
                files, warnings = collect_midi_files(path, max_depth=6)
                all_warnings.extend(warnings)
                if not files:
                    all_warnings.append(f"No MIDI files found in: {os.path.basename(path.rstrip(os.sep))}")
                seen_folders = set()
                first_file = True
                for f in files:
                    rel = os.path.relpath(f, path)
                    parts = rel.split(os.sep)
                    folder_parts = parts[:-1]
                    # Insert a folder header for each new subfolder level.
                    for i in range(len(folder_parts)):
                        folder_key = os.sep.join(folder_parts[:i + 1])
                        if folder_key not in seen_folders:
                            seen_folders.add(folder_key)
                            self._add_folder_header(folder_parts[i], depth=i)
                    # Only select the first file; adding thousands of items to the
                    # sidebar one-by-one while changing the selection each time
                    # fires currentItemChanged synchronously on the main thread for
                    # every file, which can cause severe event-loop starvation on
                    # large collections.
                    self.analyze(f, depth=len(folder_parts), select=first_file)
                    first_file = False
            else:
                self.analyze(path, sorted_insert=True)
        if all_warnings:
            QMessageBox.warning(
                self,
                "Directory Scan Warning",
                "\n".join(all_warnings),
            )

    def _add_folder_header(self, name, depth=0):
        """Insert a non-selectable bold folder-name item into the sidebar."""
        indent = "\u00A0\u00A0\u00A0\u00A0" * depth
        item = QListWidgetItem(f"{indent}{name}/")
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)   # visible but not selectable
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        self.sidebar.addItem(item)
        self._folder_count += 1
        self._update_sidebar_status()

    @staticmethod
    def _sidebar_label(name, depth):
        """Build a display label that visually indents *name* by *depth* levels.

        Depth 0 (root or individually opened file) has no prefix.
        Each level adds four non-breaking spaces of indentation.
        """
        if depth <= 0:
            return name
        indent = "\u00A0\u00A0\u00A0\u00A0" * depth  # non-breaking spaces so Qt won't collapse them
        return f"{indent}{name}"

    def analyze(self, path, depth=0, sorted_insert=False, select=True):
        # Already in the sidebar (analyzed or queued) — just select it.
        if path in self._file_sections or path in self._pending_set \
                or path == self._active_worker_path:
            self._select_sidebar_item(path)
            return

        self._file_order.append(path)
        label = self._sidebar_label(os.path.basename(path), depth)
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setData(Qt.ItemDataRole.UserRole.value + 1, label)  # base label (no tags)
        if sorted_insert:
            self._insert_file_sorted(item, path)
        else:
            self.sidebar.addItem(item)
        self._sidebar_items[path] = item
        self._visible_count += 1   # new items are always visible (pending, tags unknown)
        if select:
            self.sidebar.setCurrentItem(item)
        self.clear_button.setEnabled(True)
        self._update_sidebar_status()

        self._pending_paths.append(path)
        self._pending_set.add(path)
        # Reset progress counters when adding to an otherwise-idle queue, so
        # a new drag-and-drop batch starts fresh rather than continuing from
        # a previous run's totals.
        if self._active_worker_path is None and self._total_files == self._completed_files:
            self._total_files = 0
            self._completed_files = 0
        self._total_files += 1
        self._update_progress()
        self._start_next_worker()

    def _insert_file_sorted(self, item, path):
        """Insert *item* into the sidebar in case-insensitive order by basename.

        Only file items (those with a UserRole path) are considered for
        ordering; folder-header items are skipped.  The new item is placed
        before the first existing file item whose basename sorts after it.
        """
        key = os.path.basename(path).lower()
        for i in range(self.sidebar.count()):
            existing = self.sidebar.item(i)
            existing_path = existing.data(Qt.ItemDataRole.UserRole)
            if not existing_path:
                continue  # folder header — skip
            if key < os.path.basename(existing_path).lower():
                self.sidebar.insertItem(i, item)
                return
        self.sidebar.addItem(item)

    def _update_sidebar_status(self):
        """Refresh the file/folder count label below the sidebar.

        All values come from O(1) pre-maintained counters (_file_order length,
        _folder_count, _visible_count) — never scans the sidebar or item list.
        """
        files = len(self._file_order)
        folders = self._folder_count
        if files == 0 and folders == 0:
            self.sidebar_status_label.setText("")
            return

        has_active_filter = (
            hasattr(self, '_standard_checks') and any(self._get_active_filters())
        )
        if has_active_filter:
            file_str = f"{self._visible_count} of {files} file{'s' if files != 1 else ''}"
        else:
            file_str = f"{files} file{'s' if files != 1 else ''}"

        if folders == 0:
            self.sidebar_status_label.setText(file_str)
        else:
            self.sidebar_status_label.setText(
                f"{file_str}  ·  {folders} folder{'s' if folders != 1 else ''}"
            )

    # ------------------------------------------------------------------
    # Sidebar filter
    # ------------------------------------------------------------------

    def _get_active_filters(self):
        """Return active filter state as
        (show_standards, show_modifiers, hide_modifiers, advanced).

        show_standards: frozenset of standard keys checked for OR-inclusion;
            empty means no standard filter (show all standards).
        show_modifiers: frozenset of modifier keys in the checked (show-only) state.
        hide_modifiers: frozenset of modifier keys in the partially-checked (hide) state.
        advanced: dict of advanced filter conditions (empty = no advanced filter).
        """
        show_standards = frozenset(
            key for key, cb in self._standard_checks.items() if cb.isChecked()
        )
        show_modifiers = set()
        hide_modifiers = set()
        for key, cb in self._modifier_checks.items():
            state = cb.checkState()
            if state == Qt.CheckState.Checked:
                show_modifiers.add(key)
            elif state == Qt.CheckState.PartiallyChecked:
                hide_modifiers.add(key)
        return (show_standards, frozenset(show_modifiers), frozenset(hide_modifiers),
                self._advanced_filters)

    @staticmethod
    def _make_modifier_cycle_handler(cb):
        """Return a clicked-signal handler that enforces the desired tri-state cycle.

        PyQt's default tri-state cycle is Unchecked → PartiallyChecked → Checked.
        The desired cycle is Unchecked → Checked (show only) → PartiallyChecked (hide).

        Remapping the already-changed state is unreliable because the override changes
        what Qt uses as the starting point for the *next* click.  Instead, this handler
        tracks the logical step (0/1/2) in a closure variable and always forces the
        correct Qt state directly, ignoring whatever Qt already set.
        """
        _step = [0]  # mutable: 0=off, 1=show only (Checked), 2=hide (PartiallyChecked)
        _qt_states = [
            Qt.CheckState.Unchecked,
            Qt.CheckState.Checked,
            Qt.CheckState.PartiallyChecked,
        ]

        def handler(_=None):
            _step[0] = (_step[0] + 1) % 3
            cb.setCheckState(_qt_states[_step[0]])

        return handler

    def _on_filter_changed(self):
        """Called when any standard or modifier checkbox changes state.

        Restarts the debounce timer rather than applying immediately, so that
        rapid successive changes collapse into a single O(n) scan.
        """
        self._filter_timer.start()  # (re)starts the 100 ms single-shot timer

    def _open_advanced_filter(self):
        """Open the Advanced Filter dialog and apply any changes on OK."""
        dialog = AdvancedFilterDialog(
            self._advanced_filters,
            gs_active=self._standard_checks['GS'].isChecked(),
            xg_active=self._standard_checks['XG'].isChecked(),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._advanced_filters = dialog.get_filters()
            self._update_adv_btn()
            # Auto-check the GS standard filter if any SC version is selected,
            # and the XG standard filter if any XG level is selected.
            if self._advanced_filters.get('sc_versions'):
                self._standard_checks['GS'].setChecked(True)
            if self._advanced_filters.get('xg_levels'):
                self._standard_checks['XG'].setChecked(True)
            self._on_filter_changed()

    def _reset_all_filters(self):
        """Clear all standard checkboxes, modifier checkboxes, and advanced filters."""
        # Block signals while resetting to avoid triggering _on_filter_changed
        # once per widget; a single call at the end is sufficient.
        for cb in self._standard_checks.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        for cb in self._modifier_checks.values():
            cb.blockSignals(True)
            cb.setCheckState(Qt.CheckState.Unchecked)
            cb.blockSignals(False)
        self._advanced_filters = {}
        self._update_adv_btn()
        self._on_filter_changed()

    def _on_gs_check_changed(self, state):
        """Clear SC-version advanced filters when the GS standard checkbox is unchecked."""
        if not state and self._advanced_filters.pop('sc_versions', None):
            self._update_adv_btn()

    def _on_xg_check_changed(self, state):
        """Clear XG-level advanced filters when the XG standard checkbox is unchecked."""
        if not state and self._advanced_filters.pop('xg_levels', None):
            self._update_adv_btn()

    def _update_adv_btn(self):
        """Update the Advanced button label to show when advanced filters are active."""
        self._adv_btn.setText(
            "Advanced \u25cf" if self._advanced_filters else "Advanced\u2026")

    def _apply_sidebar_filter(self):
        """Show or hide sidebar file items based on the active filters.

        Folder-header items are always kept visible.  Pending (not yet
        analyzed) items are always shown since their tags are unknown.
        Standard filters use OR logic; modifier filters use AND logic for
        show-only and exclude logic for hide.

        This is the only place in the class that does an O(n) sidebar scan;
        it is only reached via the debounce timer (_filter_timer) so at most
        one scan runs per 100 ms burst of checkbox changes.

        Design notes:
        - Do NOT use blockSignals(True) on the sidebar.  It suppresses the
          user-facing currentItemChanged signal but not Qt's internal
          model/view sync; hiding the current item while signals are blocked
          leaves the widget in an inconsistent state that causes a hard crash.
        - Do NOT use sidebar.setUpdatesEnabled(False).  That targets the
          scroll-area frame, not the viewport where items are painted.  Use
          sidebar.viewport().setUpdatesEnabled(False) instead.
        - Pre-clear the selection before the loop when the current item will
          be hidden.  With no current item, setHidden() on any other item
          does not trigger currentItemChanged, preventing the O(n) cascade
          of auto-select → hide → auto-select → … that would otherwise fire
          _on_sidebar_selection_changed (and potentially _populate_tabs) for
          every hidden item in the list.
        - Iterate _file_order (a Python list with O(1) dict lookups via
          _sidebar_items) rather than range(sidebar.count()) + sidebar.item(i)
          (N indexed Qt calls), which is noticeably faster on large lists.
        - Skip setHidden() when the visibility state has not changed to
          reduce unnecessary Qt model/view work.
        _visible_count is maintained here so all subsequent
        _update_sidebar_status calls stay O(1).
        """
        show_standards, show_modifiers, hide_modifiers, advanced = self._get_active_filters()
        has_filter = bool(show_standards or show_modifiers or hide_modifiers or advanced)

        # Pre-clear the selection if the currently selected file item will not
        # survive the new filter.  This must happen before the loop so that
        # hiding it in the loop does not trigger the currentItemChanged cascade.
        current = self.sidebar.currentItem()
        if current:
            cur_path = current.data(Qt.ItemDataRole.UserRole)
            if cur_path:  # skip folder headers (no path data)
                cur_tags = self._file_tags.get(cur_path)
                # Only clear if the item has known tags and will be hidden.
                # Pending items (cur_tags is None) always remain visible.
                if cur_tags is not None and has_filter \
                        and not self._matches_filters(cur_tags, show_standards,
                                                      show_modifiers, hide_modifiers,
                                                      advanced):
                    self.sidebar.clearSelection()
                    self.tab_widget.clear()
                    self.file_path_edit.clear()

        visible = 0
        vp = self.sidebar.viewport()
        vp.setUpdatesEnabled(False)
        try:
            for path in self._file_order:
                item = self._sidebar_items.get(path)
                if item is None:
                    continue
                tags = self._file_tags.get(path)
                show = (tags is None) or (not has_filter) \
                    or self._matches_filters(tags, show_standards,
                                             show_modifiers, hide_modifiers, advanced)
                if item.isHidden() == show:   # state needs to change
                    item.setHidden(not show)
                if show:
                    visible += 1
        finally:
            vp.setUpdatesEnabled(True)

        self._visible_count = visible
        self._update_sidebar_status()

    @staticmethod
    def _matches_filters(tags, show_standards, show_modifiers, hide_modifiers,
                         advanced=None):
        """Return True if *tags* satisfies the active filter state.

        *tags* is the dict stored in _file_tags (basic tags merged with filter summary).
        show_standards: OR logic — file must match at least one (empty = no standard filter).
        show_modifiers: AND logic — file must have all listed tags.
        hide_modifiers: file must have none of the listed tags.
        advanced: optional dict of advanced filter conditions (empty/None = no constraint).
        """
        if show_standards:
            file_std = tags.get('standard', '')
            matched = False
            for s in show_standards:
                if s == 'unknown' and not file_std:
                    matched = True
                    break
                if s == file_std:
                    matched = True
                    break
            if not matched:
                return False
        for key in show_modifiers:
            if key == 'assumed' and not tags.get('assumed'):
                return False
            if key == 'warnings' and not tags.get('has_warnings'):
                return False
            if key == 'KAR' and not tags.get('is_karaoke'):
                return False
        for key in hide_modifiers:
            if key == 'assumed' and tags.get('assumed'):
                return False
            if key == 'warnings' and tags.get('has_warnings'):
                return False
            if key == 'KAR' and tags.get('is_karaoke'):
                return False
        if advanced and not _matches_advanced_filters(tags, advanced):
            return False
        return True

    def _clear_files(self):
        self._pending_paths.clear()
        self._pending_set.clear()
        self._sidebar_items.clear()
        self._file_tags.clear()
        self._folder_count = 0
        self._visible_count = 0
        self._file_sections.clear()
        self._file_order.clear()
        self.sidebar.clear()
        self.tab_widget.clear()
        self.file_path_edit.clear()
        self.clear_button.setEnabled(False)
        self.sidebar_status_label.setText("")
        self.statusBar().showMessage("Ready — open a MIDI file to begin.")
        self._total_files = 0
        self._completed_files = 0
        self._progress_bar.setVisible(False)

    def _update_progress(self):
        """Show or update the status-bar progress bar during multi-file analysis."""
        if self._total_files < 2:
            # Single file — no progress bar needed.
            self._progress_bar.setVisible(False)
            return
        self._progress_bar.setMaximum(self._total_files)
        self._progress_bar.setValue(self._completed_files)
        self._progress_bar.setVisible(True)
        if self._completed_files >= self._total_files:
            self._progress_bar.setVisible(False)

    def _start_next_worker(self):
        if self._active_worker_path is not None or not self._pending_paths:
            return
        path = self._pending_paths.popleft()
        self._pending_set.discard(path)
        self._active_worker_path = path
        self.statusBar().showMessage(f"Examining: {os.path.basename(path)}")
        worker = AnalysisWorker(path)
        worker.finished.connect(self._on_analysis_done)
        worker.error.connect(self._on_analysis_error)
        # deleteLater schedules C++ destruction via Qt's event loop.
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        # Move the current worker into _retired_workers BEFORE overwriting
        # self.worker.  The assignment self.worker = worker would otherwise
        # drop the old wrapper's refcount to zero, triggering immediate Python
        # GC and QThread::~QThread() while the thread is still alive in
        # sip_api_end_thread() — a fatal Qt abort.  The deque keeps the
        # wrapper alive; its maxlen ensures entries are released only after
        # at least one more full worker cycle has completed, by which time
        # the previous thread has truly exited.
        if self.worker is not None:
            self._retired_workers.append(self.worker)
        self.worker = worker
        worker.start()

    def _on_analysis_done(self, text, standard, has_warnings, assumed, is_karaoke, fsum):
        path = self._active_worker_path
        self._active_worker_path = None
        # Use _sidebar_items (O(1) dict) instead of _file_order (O(n) list) to
        # check whether this file is still active.  Both are cleared together
        # in _clear_files() and populated together in analyze().
        if path not in self._sidebar_items:
            # File was cleared while the worker was running; discard result.
            self._start_next_worker()
            return
        # Store raw text; _split_sections() is deferred until the file is first
        # viewed so that the main thread is not blocked parsing every file's
        # output up-front during a large batch analysis.
        self._file_sections[path] = text
        # Store per-file tags merged with the filter summary so both basic and
        # advanced filters can evaluate this file with O(1) dict lookups.
        self._file_tags[path] = {
            'standard':     standard,
            'has_warnings': has_warnings,
            'assumed':      assumed,
            'is_karaoke':   is_karaoke,
            **fsum,
        }
        # Color and tag the sidebar item for this file — O(1) via dict.
        item = self._sidebar_items.get(path)
        if item:
            _apply_standard_style(item, standard, has_warnings, assumed, is_karaoke)
            # Apply the active filter to this newly analyzed item.
            # The item was visible while pending; decrement _visible_count if
            # the filter now hides it.  _update_sidebar_status() reads the
            # counter, so this stays O(1) even during bulk analysis.
            # If this item is currently selected, clear the selection before
            # hiding it — same pre-clear pattern as _apply_sidebar_filter —
            # to prevent the currentItemChanged auto-select cascade.
            show_standards, show_modifiers, hide_modifiers, advanced = \
                self._get_active_filters()
            has_filter = bool(show_standards or show_modifiers or hide_modifiers
                              or advanced)
            if has_filter and not self._matches_filters(self._file_tags[path],
                                                        show_standards, show_modifiers,
                                                        hide_modifiers, advanced):
                if self.sidebar.currentItem() is item:
                    self.sidebar.clearSelection()
                    self.tab_widget.clear()
                    self.file_path_edit.clear()
                item.setHidden(True)
                self._visible_count -= 1
                self._update_sidebar_status()
        current = self.sidebar.currentItem()
        if current and current.data(Qt.ItemDataRole.UserRole) == path:
            self._populate_tabs(path)
        self._completed_files += 1
        self._update_progress()
        if self._pending_paths:
            self.statusBar().showMessage(f"Examined: {os.path.basename(path)}")
        else:
            self.statusBar().showMessage("All files examined.")
        self._start_next_worker()

    def _on_analysis_error(self, message):
        path = self._active_worker_path
        self._active_worker_path = None
        if path not in self._sidebar_items:
            self._start_next_worker()
            return
        self._file_sections[path] = [("Error", f"Error: {message}")]
        current = self.sidebar.currentItem()
        if current and current.data(Qt.ItemDataRole.UserRole) == path:
            self._populate_tabs(path)
        self._completed_files += 1
        self._update_progress()
        self.statusBar().showMessage(f"Error: {os.path.basename(path)}")
        self._start_next_worker()

    def _populate_tabs(self, path):
        self.tab_widget.clear()
        raw = self._file_sections.get(path, [])
        # Lazy parse: _on_analysis_done stores raw text (str) to avoid blocking
        # the main thread for every file during batch analysis.  Parse here on
        # first view and replace the stored value with the parsed list so
        # subsequent views are free.
        if isinstance(raw, str):
            raw = _split_sections(raw)
            self._file_sections[path] = raw
        for label, content in raw:
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
        if not path:  # folder header items have no UserRole data
            return
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
            if any(
                u.toLocalFile().lower().endswith((".mid", ".midi"))
                or os.path.isdir(u.toLocalFile())
                for u in event.mimeData().urls()
            ):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".mid", ".midi")) or os.path.isdir(path):
                paths.append(path)
        if paths:
            self._open_paths(paths)


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

    # If file paths or directories were passed as command-line arguments, open them immediately.
    cli_paths = [
        arg for arg in sys.argv[1:]
        if arg.lower().endswith((".mid", ".midi")) or os.path.isdir(arg)
    ]
    if cli_paths:
        window._open_paths(cli_paths)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
