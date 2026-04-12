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
        QVBoxLayout, QHBoxLayout,
        QPushButton, QCheckBox, QGroupBox, QLabel, QLineEdit,
        QTextEdit, QFileDialog, QTabWidget, QMenu,
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

from midi_examiner import __version__, analyze_midi_file, print_results, collect_midi_files

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

    # emits (formatted text, detected_standard or "", has_warnings, standard_assumed, is_karaoke)
    finished = pyqtSignal(str, str, bool, bool, bool)
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
            standard = results.get("detected_standard") or ""
            has_warnings = bool(results.get("warnings"))
            assumed = bool(results.get("standard_assumed"))
            is_karaoke = bool(results.get("karaoke"))
            self.finished.emit(output.getvalue(), standard, has_warnings, assumed, is_karaoke)
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
        self._file_tags = {}       # path -> {standard, has_warnings, assumed, is_karaoke}
        self._folder_count = 0     # number of folder-header rows in the sidebar
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
                    all_warnings.append(f"No MIDI files found in: {os.path.basename(path)}")
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
        """Return active filter state as (show_standards, show_modifiers, hide_modifiers).

        show_standards: frozenset of standard keys checked for OR-inclusion;
            empty means no standard filter (show all standards).
        show_modifiers: frozenset of modifier keys in the checked (show-only) state.
        hide_modifiers: frozenset of modifier keys in the partially-checked (hide) state.
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
        return show_standards, frozenset(show_modifiers), frozenset(hide_modifiers)

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
        show_standards, show_modifiers, hide_modifiers = self._get_active_filters()
        has_filter = bool(show_standards or show_modifiers or hide_modifiers)

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
                                                      show_modifiers, hide_modifiers):
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
                                             show_modifiers, hide_modifiers)
                if item.isHidden() == show:   # state needs to change
                    item.setHidden(not show)
                if show:
                    visible += 1
        finally:
            vp.setUpdatesEnabled(True)

        self._visible_count = visible
        self._update_sidebar_status()

    @staticmethod
    def _matches_filters(tags, show_standards, show_modifiers, hide_modifiers):
        """Return True if *tags* satisfies the active filter state.

        *tags* is the dict stored in _file_tags.
        show_standards: OR logic — file must match at least one (empty = no standard filter).
        show_modifiers: AND logic — file must have all listed tags.
        hide_modifiers: file must have none of the listed tags.
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

    def _on_analysis_done(self, text, standard, has_warnings, assumed, is_karaoke):
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
        # Store per-file tags so the sidebar filter can evaluate this file.
        self._file_tags[path] = {
            'standard': standard,
            'has_warnings': has_warnings,
            'assumed': assumed,
            'is_karaoke': is_karaoke,
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
            show_standards, show_modifiers, hide_modifiers = self._get_active_filters()
            has_filter = bool(show_standards or show_modifiers or hide_modifiers)
            if has_filter and not self._matches_filters(self._file_tags[path],
                                                        show_standards, show_modifiers,
                                                        hide_modifiers):
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
