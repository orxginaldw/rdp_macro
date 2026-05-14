import os
import subprocess
import tempfile
import uuid
import winreg
import zipfile
import pycurl
import win32com.client
import win32net
import win32netcon
from datetime import datetime, timedelta, timezone
from github import Github

class rdp_wrapper:    # based on https://www.youtube.com/watch?v=4Oexj5zf84I
    def __init__(self):
        self.github = Github()

        self.rdpwrap = os.path.join(os.environ["ProgramFiles"], "RDP Wrapper", "rdpwrap.ini")

    def execute_command(self, command):
        name = f"RDP_{uuid.uuid4().hex[:12]}"
        scheduler = win32com.client.Dispatch("Schedule.Service")
        scheduler.Connect()
        task = scheduler.NewTask(0)
        task.Settings.AllowDemandStart = True
        task.Principal.UserId = "RDP"
        task.Principal.LogonType = 3
        task.Principal.RunLevel = 0
        task.Triggers.Create(1).StartBoundary = "9999-12-31T00:00:00"
        action = task.Actions.Create(0)
        action.Path = "cmd.exe"
        action.Arguments = f"/c {command}"
        root = scheduler.GetFolder("\\")
        root.RegisterTaskDefinition(name, task, 6, "RDP", "RDP", 3)
        root.GetTask(name).Run(None)
        root.DeleteTask(name, 0)

    def rdp_winst(self, arg):
        asset = next(
            rdp for rdp in self.github.get_repo("stascorp/rdpwrap")
            .get_latest_release().get_assets()
            if rdp.name.endswith(".zip")
        )

        zip_path = os.path.join(tempfile.gettempdir(), asset.name)

        with open(zip_path, "wb") as output_file:
            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, asset.browser_download_url)
            curl.setopt(pycurl.WRITEDATA, output_file)
            curl.setopt(pycurl.FOLLOWLOCATION, 1)
            curl.perform()
            curl.close()

        extract_path = os.path.join(tempfile.gettempdir(), os.path.splitext(asset.name)[0])
        os.makedirs(extract_path, exist_ok=True)

        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_path)

        for root, _, files in os.walk(extract_path):
            if "RDPWInst.exe" in files:
                subprocess.run(
                    [os.path.join(root, "RDPWInst.exe"), arg],
                    cwd=root,
                )
                self.create_user()
                return

    def update_ini(self):
        now = datetime.now(timezone.utc)
        file_time = datetime.fromtimestamp(os.stat(self.rdpwrap).st_mtime, tz=timezone.utc)
        if now - file_time < timedelta(days=1):    # avoid rate limit
            return
        commit_time = self.github.get_repo("sebaxakerhtc/rdpwrap.ini").get_commits(
            path="rdpwrap.ini",
        )[0].commit.committer.date
        if commit_time > file_time:
            with open(self.rdpwrap, "wb") as handle:
                handle.write(
                    self.github.get_repo("sebaxakerhtc/rdpwrap.ini").get_contents("rdpwrap.ini").decoded_content
                )
        else:
            os.utime(self.rdpwrap, None)

    def create_user(self):
        try:
            win32net.NetUserAdd(
                None,
                1,
                {
                    "name": "RDP",
                    "password": "RDP",
                    "priv": win32netcon.USER_PRIV_USER,
                    "flags": win32netcon.UF_NORMAL_ACCOUNT | win32netcon.UF_SCRIPT | win32netcon.UF_DONT_EXPIRE_PASSWD,    # no password expiry after 3 months
                },
            )
            win32net.NetLocalGroupAddMembers(
                None,
                "Remote Desktop Users",
                3,
                [{"domainandname": f"{os.environ['COMPUTERNAME']}\\RDP"}],
            )
        except Exception:    # ignore if already exists
            pass

    def check_install(self):    # ui display
        return os.path.exists(self.rdpwrap)

    def install(self):
        if not self.check_install():    # install path
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Terminal Server",
                0,
                winreg.KEY_SET_VALUE,
            ) as i:
                winreg.SetValueEx(
                    i,
                    "fDenyTSConnections",   # enable remote desktop
                    0,
                    winreg.REG_DWORD,
                    0,
                )

            win32com.client.Dispatch("HNetCfg.FwPolicy2").EnableRuleGroup(7, "Remote Desktop", True)

            self.rdp_winst("-i")    # update path already handles -o

            with open(self.rdpwrap, "wb") as handle:    # update ini file
                handle.write(
                    self.github.get_repo("sebaxakerhtc/rdpwrap.ini")
                    .get_contents("rdpwrap.ini")
                    .decoded_content
                )

            return

        self.update_ini()   # update path

    def uninstall(self):
        if self.check_install():
            self.rdp_winst("-u")    # you still have to manually remove user, settings
