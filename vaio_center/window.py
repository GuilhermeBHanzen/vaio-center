"""Main window: page list on the left, the selected page on the right."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, pages):
        super().__init__(application=app, title="VAIO Control Center", default_width=900, default_height=640)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hexpand=True, vexpand=True)
        for page in pages:
            self.stack.add_titled(page, page.key, page.title)
        sidebar = Gtk.StackSidebar(stack=self.stack)
        sidebar.set_size_request(200, -1)

        body = Gtk.Box()
        body.append(sidebar)
        body.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        body.append(self.stack)

        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(body)
        self.set_content(view)
        self.stack.connect("notify::visible-child", lambda *_args: self.refresh_visible())

    def refresh_visible(self):
        page = self.stack.get_visible_child()
        if page is not None:
            page.refresh()
