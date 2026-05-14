import sys
import subprocess
import qreactor
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wrapper import rdp_wrapper

app = QApplication(sys.argv)
qreactor.install()

from twisted.internet import reactor
from rdpy.protocol.rdp import rdp
from rdpy.ui.qt6 import RDPClientQt

class config_panel(QWidget):
    def __init__(self, wrapper, app):
        super().__init__()
        self.wrapper = wrapper
        self.app = app
        self.connection = None
        self.client = None
        self.window = None
        self.setWindowTitle("Task Scheduler")
        self.resize(480, 240)
        self.setMinimumSize(400, 210)

        main_column = QVBoxLayout(self)
        main_column.setContentsMargins(16, 16, 16, 16)
        main_column.setSpacing(12)

        self.install_button = QPushButton("Install")
        main_column.addWidget(self.install_button)

        command_row = QHBoxLayout()
        command_row.setSpacing(10)
        command_label = QLabel("Command:")
        command_row.addWidget(command_label)
        self.command_line = QLineEdit()
        command_row.addWidget(self.command_line, stretch=1)
        main_column.addLayout(command_row)

        action_button_row = QHBoxLayout()
        action_button_row.setSpacing(10)
        self.execute_command_button = QPushButton("Execute Command")
        self.show_preview_button = QPushButton("Show Preview")
        self.hide_preview_button = QPushButton("Hide Preview")
        for button in (
            self.execute_command_button,
            self.show_preview_button,
            self.hide_preview_button,
        ):
            action_button_row.addWidget(button, stretch=1)
        main_column.addLayout(action_button_row)

        font_standard = QFont(self.font())
        font_standard.setPointSize(14)
        font_heading = QFont(self.font())
        font_heading.setPointSize(16)
        self.install_button.setFont(font_standard)
        command_label.setFont(font_heading)
        for widget in (
            self.command_line,
            self.execute_command_button,
            self.show_preview_button,
            self.hide_preview_button,
        ):
            widget.setFont(font_standard)
        for widget in (
            self.install_button,
            self.command_line,
            self.execute_command_button,
            self.show_preview_button,
            self.hide_preview_button,
        ):
            widget.setMinimumHeight(40)

        self.session_widgets = (
            self.command_line,
            self.execute_command_button,
            self.show_preview_button,
            self.hide_preview_button,
        )

        self.install_button.clicked.connect(self.on_install_clicked)
        self.execute_command_button.clicked.connect(
            lambda: self.wrapper.execute_command(self.command_line.text()),
        )
        self.show_preview_button.clicked.connect(self.on_show_preview_clicked)
        self.hide_preview_button.clicked.connect(self.on_hide_preview_clicked)

        if self.wrapper.check_install():
            self.wrapper.update_ini()
            self.try_connect_rdp()
        self.apply_installed_state()

    def confirm_restart(self):
        return QMessageBox.question(
            self,
            "Restart required",
            "To complete the change fully, restart the computer.\n\nRestart now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def try_connect_rdp(self):
        if not self.wrapper.check_install() or self.connection is not None:
            return
        self.client = rdp_session(self)
        self.connection = reactor.connectTCP("127.0.0.1", 3389, self.client)

    def apply_installed_state(self):
        installed = self.wrapper.check_install()
        for widget in self.session_widgets:
            widget.setEnabled(installed)
        self.install_button.setText("Uninstall" if installed else "Install")

    def on_show_preview_clicked(self):
        if self.window is None:
            return
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def on_hide_preview_clicked(self):
        if self.window is not None:
            self.window.hide()

    def on_install_clicked(self):
        if self.wrapper.check_install():
            if self.connection is not None:
                self.connection.disconnect()
            self.clear_connection()
            self.wrapper.uninstall()
            if self.confirm_restart():
                subprocess.Popen(["shutdown", "/r", "/t", "0"], close_fds=True)
            self.apply_installed_state()
            return
        self.wrapper.install()
        if self.confirm_restart():
            subprocess.Popen(["shutdown", "/r", "/t", "0"], close_fds=True)
        else:
            self.try_connect_rdp()
        self.apply_installed_state()

    def clear_connection(self, disconnect=False):
        if disconnect and self.connection is not None:
            self.connection.disconnect()
        self.connection = None
        self.client = None
        if self.window is not None:
            self.window.close()
            self.window = None

    def closeEvent(self, event):
        event.accept()
        self.clear_connection(disconnect=True)
        reactor.stop()
        self.app.quit()


class rdp_session(rdp.ClientFactory):
    def __init__(self, panel):
        self.panel = panel

    def buildObserver(self, controller, addr):
        self.client = RDPClientQt(controller, 960, 540)
        window = self.client.getWidget()
        window.setWindowTitle("RDP")
        window.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.panel.window = window
        window.hide()
        controller.setUsername("RDP")
        controller.setPassword("RDP")
        controller.setHostname("127.0.0.1")
        return self.client

    def clientConnectionLost(self, connector, reason):
        self.panel.clear_connection()

    def clientConnectionFailed(self, connector, reason):
        self.panel.clear_connection()


def main():
    wrapper = rdp_wrapper()
    panel = config_panel(wrapper, app)
    panel.show()
    reactor.runReturn()
    app.exec()


main()
