import sys
import re
import os
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWebEngineCore import *
from PyQt5.QtGui import *
from PyQt5.QtWebChannel import QWebChannel
class Settings:
    def __init__(self):
        self._settings = {
            "homepage": "https://duckduckgo.com",
            "theme": "Light",
            "download_path": os.path.expanduser("~/Downloads")
        }
    def get(self, key, default=None):
        return self._settings.get(key, default)

    def set(self, key, value):
        self._settings[key] = value
settings = Settings()
class CustomWebEngineView(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page().profile().downloadRequested.connect(self.handle_download)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.custom_context_menu)
        self.setup_middle_click_handler()
    def setup_middle_click_handler(self):
        js_script = """
        document.addEventListener('mouseup', function(e) {
            if (e.button === 1) { // Middle button
                var target = e.target;
                while (target && target.tagName !== 'A') {
                    target = target.parentElement;
                }
                if (target && target.href) {
                    e.preventDefault();
                    window.qt.middleClickLink(target.href);
                }
            }
        }, true);
        """
        self.channel = QWebChannel()
        self.handler = MiddleClickHandler(self)
        self.channel.registerObject("qt", self.handler)
        self.page().setWebChannel(self.channel)
        self.page().loadFinished.connect(lambda: self.page().runJavaScript(js_script))
    def custom_context_menu(self, pos):
        menu = self.page().createStandardContextMenu()
        menu.addSeparator()
        hit_test = self.page().hitTestContent(pos)
        if hit_test.linkUrl().isValid():
            open_in_new_tab = menu.addAction("Open Link in New Tab")
            open_in_new_tab.triggered.connect(lambda: self.open_link_in_new_tab(hit_test.linkUrl()))
        if hit_test.linkUrl().isValid():
            download_link = menu.addAction("Download Link")
            download_link.triggered.connect(lambda: self.page().download(hit_test.linkUrl(), ""))
        menu.exec_(self.mapToGlobal(pos))
    def open_link_in_new_tab(self, url):
        parent = self
        while parent and not isinstance(parent, ModernWebBrowser):
            parent = parent.parent()
        if parent:
            parent.add_new_tab(url.toString())
    def createWindow(self, type_):
        if type_ == QWebEnginePage.WebBrowserTab:
            browser = self.window()
            while browser and not isinstance(browser, ModernWebBrowser):
                browser = browser.parent().window()
            if browser:
                return browser.create_tab_for_external_request()
        return None
    def handle_download(self, download):
        download_path = settings.get("download_path")
        if not os.path.exists(download_path):
            os.makedirs(download_path)
        suggested_filename = QFileInfo(download.url().path()).fileName()
        if not suggested_filename:
            suggested_filename = "download"
        file_path = os.path.join(download_path, suggested_filename)
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save File", 
            file_path,
            "All Files (*.*)"
        )
        if file_path:
            download.setPath(file_path)
            download.accept()
            download.downloadProgress.connect(lambda received, total: 
                self.window().statusBar().showMessage(f"Downloading: {received/total*100:.1f}%"))
            download.finished.connect(lambda: 
                self.window().statusBar().showMessage(f"Download complete: {os.path.basename(file_path)}", 3000))
        else:
            download.cancel()
class MiddleClickHandler(QObject):
    def __init__(self, web_view):
        super().__init__()
        self.web_view = web_view
    @pyqtSlot(str)
    def middleClickLink(self, url):
        self.web_view.open_link_in_new_tab(QUrl(url))
class TabBarWithPlus(QTabBar):
    addTabClicked = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        QTimer.singleShot(0, self.setup_plus_button)
    def setup_plus_button(self):
        self.plus_button = QToolButton(self)
        self.plus_button.setText("+")
        self.plus_button.setCursor(Qt.PointingHandCursor)
        self.plus_button.setAutoRaise(True)
        self.plus_button.clicked.connect(self.emitAddTab)
        self.plus_button.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                font-size: 16px;
                padding: 0 6px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
                border-radius: 4px;
            }
        """)
        self.plus_button.show()
        self.update_plus_button_position()
    def emitAddTab(self):
        self.addTabClicked.emit()
    def update_plus_button_position(self):
        if not hasattr(self, 'plus_button') or self.plus_button is None:
            return 
        total_width = 0
        for i in range(self.count()):
            total_width += self.tabRect(i).width()
        btn_width = self.plus_button.sizeHint().width()
        x = min(total_width + 5, self.width() - btn_width - 5)
        y = (self.height() - self.plus_button.sizeHint().height()) // 2
        self.plus_button.move(x, y)
        self.plus_button.raise_()
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.update_plus_button_position)
    def tabLayoutChange(self):
        super().tabLayoutChange()
        QTimer.singleShot(0, self.update_plus_button_position)
    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.LayoutRequest:
            QTimer.singleShot(0, self.update_plus_button_position)
        return result
class ModernWebBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("whiskweb – soft paws strong privacy")
        self.resize(1400, 900)
        QTimer.singleShot(0, self.setup_ui)
    def setup_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        self.tab_widget = QTabWidget()
        custom_tab_bar = TabBarWithPlus()
        custom_tab_bar.addTabClicked.connect(self.add_new_tab)
        self.tab_widget.setTabBar(custom_tab_bar)
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        nav_toolbar = self.create_navigation_toolbar()
        self.create_menus()
        main_layout.addWidget(nav_toolbar)
        main_layout.addWidget(self.tab_widget)
        self.statusBar()
        QTimer.singleShot(100, lambda: self.add_new_tab(settings.get("homepage")))
        self.apply_stylesheet()
    def create_tab_for_external_request(self):
        """Create a new tab for middle-click or external navigation requests"""
        webview = CustomWebEngineView(self)
        index = self.tab_widget.addTab(webview, "New Tab")
        self.tab_widget.setCurrentIndex(index)
        webview.urlChanged.connect(lambda qurl, view=webview: 
                                  self.update_url_bar(qurl, view))
        webview.loadFinished.connect(
            lambda ok, view=webview, idx=index: 
            self.handle_load_finished(ok, view, idx)
        )
        return webview
    def create_navigation_toolbar(self):
        nav_toolbar = QToolBar("Navigation")
        nav_toolbar.setMovable(False)
        nav_actions = [
            ("Back", "go-previous", self.go_back),
            ("Forward", "go-next", self.go_forward),
            ("Refresh", "view-refresh", self.refresh_page)
        ]
        for label, icon_name, handler in nav_actions:
            if QIcon.hasThemeIcon(icon_name):
                action = QAction(QIcon.fromTheme(icon_name), label, self)
            else:
                action = QAction(label, self)
            action.triggered.connect(handler)
            nav_toolbar.addAction(action)
        if QIcon.hasThemeIcon("download"):
            downloads_action = QAction(QIcon.fromTheme("download"), "Downloads", self)
        else:
            downloads_action = QAction("Downloads", self)
        downloads_action.triggered.connect(self.show_downloads)
        nav_toolbar.addAction(downloads_action)
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Enter URL or search term")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        nav_toolbar.addWidget(self.url_bar)
        return nav_toolbar
    def create_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        settings_menu = menu_bar.addMenu("Settings")
        new_tab_action = QAction("New Tab", self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.triggered.connect(self.add_new_tab)
        file_menu.addAction(new_tab_action)
        download_action = QAction("Downloads", self)
        download_action.setShortcut("Ctrl+J")
        download_action.triggered.connect(self.show_downloads)
        file_menu.addAction(download_action)
        settings_action = QAction("Whiskweb Settings", self)
        settings_action.triggered.connect(self.open_settings)
        settings_menu.addAction(settings_action)
    def apply_stylesheet(self):
        self.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background-color: #f0f0f0;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                color: black;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #4CAF50;
            }
        """)
    def add_new_tab(self, url=None):
        try:
            webview = CustomWebEngineView(self)
            homepage = url or settings.get("homepage")
            if not homepage.startswith(('http://', 'https://')):
                homepage = 'https://' + homepage
            qurl = QUrl(homepage)
            if not qurl.isValid():
                qurl = QUrl("https://duckduckgo.com")
            webview.load(qurl)
            loading_title = "Loading..."
            index = self.tab_widget.addTab(webview, loading_title)
            self.tab_widget.setCurrentIndex(index)
            webview.urlChanged.connect(lambda qurl, view=webview: 
                                    self.update_url_bar(qurl, view))
            webview.loadFinished.connect(
                lambda ok, view=webview, idx=index: 
                self.handle_load_finished(ok, view, idx)
            )
            return webview
        except Exception as e:
            QMessageBox.warning(self, "Tab Error", f"Could not open new tab: {str(e)}")
            return None
    def handle_load_finished(self, success, view, index):
        if index < self.tab_widget.count():
            if success:
                title = view.page().title() or "New Tab"
                title = (title[:20] + '...') if len(title) > 23 else title
                self.tab_widget.setTabText(index, title)
            else:
                self.tab_widget.setTabText(index, "Error")
    def update_tab_title(self, view, index):
        if index < self.tab_widget.count():
            title = view.page().title() or "New Tab"
            title = (title[:20] + '...') if len(title) > 23 else title
            self.tab_widget.setTabText(index, title)
    def close_tab(self, index):
        # safety check
        if index < 0 or index >= self.tab_widget.count():
            return
        if self.tab_widget.count() > 1:
            widget = self.tab_widget.widget(index)
            self.tab_widget.removeTab(index)
            if widget:
                widget.deleteLater()
        else:
            self.add_new_tab()
            QTimer.singleShot(100, lambda: self.tab_widget.removeTab(0) if self.tab_widget.count() > 1 else None)
    def navigate_to_url(self):
        url = self.url_bar.text().strip()
        if not re.match(r'^https?://\S+\.\S+$', url):
            url = f'https://duckduckgo.com/?q={url.replace(" ", "+")}'
        elif not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        current_webview = self.tab_widget.currentWidget()
        if current_webview and isinstance(current_webview, QWebEngineView):
            qurl = QUrl(url)
            if qurl.isValid():
                current_webview.load(qurl)
            else:
                QMessageBox.warning(self, "Invalid URL", "The URL entered is not valid.")
    def update_url_bar(self, qurl, view):
        if view == self.tab_widget.currentWidget():
            self.url_bar.setText(qurl.toString())
    def go_back(self):
        current = self.tab_widget.currentWidget()
        if current and isinstance(current, QWebEngineView):
            current.back()
    def go_forward(self):
        current = self.tab_widget.currentWidget()
        if current and isinstance(current, QWebEngineView):
            current.forward()
    def refresh_page(self):
        current = self.tab_widget.currentWidget()
        if current and isinstance(current, QWebEngineView):
            current.reload()
    def show_downloads(self):
        """Show downloads dialog"""
        download_dialog = QDialog(self)
        download_dialog.setWindowTitle("Downloads")
        download_dialog.setMinimumSize(500, 300)
        layout = QVBoxLayout()
        info_label = QLabel("Download location: " + settings.get("download_path"))
        layout.addWidget(info_label)
        open_folder_btn = QPushButton("Open Downloads Folder")
        open_folder_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(settings.get("download_path"))
        ))
        layout.addWidget(open_folder_btn)
        change_folder_btn = QPushButton("Change Download Location")
        change_folder_btn.clicked.connect(self.change_download_location)
        layout.addWidget(change_folder_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(download_dialog.accept)
        layout.addWidget(close_btn)
        download_dialog.setLayout(layout)
        download_dialog.exec_()
    def change_download_location(self):
        """Let user change download location"""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Download Location",
            settings.get("download_path"),
            QFileDialog.ShowDirsOnly
        )
        if folder:
            settings.set("download_path", folder)
            QMessageBox.information(self, "Downloads", f"Download location changed to:\n{folder}")
    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Whiskweb Settings")
        dialog.setMinimumSize(500, 300)
        layout = QVBoxLayout()
        settings_tabs = QTabWidget()
        general_tab = QWidget()
        general_layout = QVBoxLayout()
        homepage_layout = QHBoxLayout()
        homepage_label = QLabel("Homepage:")
        homepage_input = QLineEdit(settings.get("homepage"))
        homepage_layout.addWidget(homepage_label)
        homepage_layout.addWidget(homepage_input)
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_combo = QComboBox()
        theme_combo.addItems(["Light", "Dark"])
        theme_combo.setCurrentText(settings.get("theme"))
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(theme_combo)
        downloads_group = QGroupBox("Downloads")
        downloads_layout = QVBoxLayout()
        dl_path_layout = QHBoxLayout()
        dl_path_label = QLabel("Download Location:")
        dl_path_input = QLineEdit(settings.get("download_path"))
        dl_path_input.setReadOnly(True)
        dl_path_button = QPushButton("Browse...")
        dl_path_button.clicked.connect(lambda: self.browse_download_path(dl_path_input))
        dl_path_layout.addWidget(dl_path_label)
        dl_path_layout.addWidget(dl_path_input)
        dl_path_layout.addWidget(dl_path_button)
        downloads_layout.addLayout(dl_path_layout)
        downloads_group.setLayout(downloads_layout)
        general_layout.addLayout(homepage_layout)
        general_layout.addLayout(theme_layout)
        general_layout.addWidget(downloads_group)
        general_layout.addStretch()
        general_tab.setLayout(general_layout)
        settings_tabs.addTab(general_tab, "General")
        layout.addWidget(settings_tabs)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        dialog.setLayout(layout)
        if dialog.exec_() == QDialog.Accepted:
            settings.set("homepage", homepage_input.text())
            settings.set("theme", theme_combo.currentText())
            settings.set("download_path", dl_path_input.text())
            QMessageBox.information(self, "Settings", "Settings saved successfully!")
    def browse_download_path(self, input_field):
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Download Location",
            input_field.text(),
            QFileDialog.ShowDirsOnly
        )
        if folder:
            input_field.setText(folder)
def main():
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Whiskweb")
    app.setOrganizationName("WhiskwebOrg")
    profile = QWebEngineProfile.defaultProfile()
    try:
        browser = ModernWebBrowser()
        browser.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Critical error: {str(e)}")
        try:
            error_app = QApplication(sys.argv)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("WhiskWeb crashed during startup")
            msg.setInformativeText(f"Error: {str(e)}")
            msg.setWindowTitle("WhiskWeb Error")
            msg.exec_()
        except:
            pass
        sys.exit(1)
if __name__ == "__main__":
    main()