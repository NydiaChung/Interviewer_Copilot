import sys
import Cocoa
from PyObjCTools import AppHelper

class TransparentWindow(Cocoa.NSWindow):
    def canBecomeKeyWindow(self):
        return True

class AppDelegate(Cocoa.NSObject):
    def applicationDidFinishLaunching_(self, notification):
        # Screen dimensions
        screen = Cocoa.NSScreen.mainScreen()
        frame = screen.frame()
        
        # Window attributes
        mask = Cocoa.NSBorderlessWindowMask | Cocoa.NSResizableWindowMask
        self.window = TransparentWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            Cocoa.NSMakeRect(100, 100, 400, 300),
            mask,
            Cocoa.NSBackingStoreBuffered,
            False
        )
        
        # Transparency and ordering
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(Cocoa.NSColor.clearColor())
        self.window.setLevel_(Cocoa.NSFloatingWindowLevel) # Always on top
        self.window.setIgnoresMouseEvents_(True) # Click through
        self.window.setCollectionBehavior_(Cocoa.NSWindowCollectionBehaviorTransient | Cocoa.NSWindowCollectionBehaviorIgnoresCycle | Cocoa.NSWindowCollectionBehaviorFullScreenAuxiliary)
        # MacOS 14.4 NSWindowSharingNone is DEPRECATED and removed. Use CoreGraphics to prevent screen sharing if possible or just accept NSWindowSharingNone doesn't work for hiding from sharing.
        
        # Add some text
        text_view = Cocoa.NSTextView.alloc().initWithFrame_(Cocoa.NSMakeRect(0, 0, 400, 300))
        text_view.setString_("Hello from transparent PyObjC!")
        text_view.setBackgroundColor_(Cocoa.NSColor.colorWithCalibratedRed_green_blue_alpha_(0, 0, 0, 0.5))
        text_view.setTextColor_(Cocoa.NSColor.yellowColor())
        text_view.setFont_(Cocoa.NSFont.systemFontOfSize_(24))
        self.window.contentView().addSubview_(text_view)
        
        self.window.makeKeyAndOrderFront_(None)

def main():
    app = Cocoa.NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    AppHelper.runEventLoop()

if __name__ == '__main__':
    main()
