"""打包成单文件 exe（内置 Python 运行环境和 7-Zip）：py build.py → dist\\UndoExtract.exe

需要本机装有 64 位 7-Zip（从中复制 7z.exe / 7z.dll）；PyInstaller 会自动装进项目内的 .venv。
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import venv

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(ROOT, "undo_extract.pyw")
VENV_PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
SEVEN_ZIP = os.path.join(os.environ.get("ProgramW6432") or os.environ["ProgramFiles"], "7-Zip")
BUNDLED = ("7z.exe", "7z.dll", "License.txt")
NAME = "UndoExtract"

# exe 的“属性 → 详细信息”，没有这些元数据的程序更容易被杀毒软件当成可疑
VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}),
  kids=[
    StringFileInfo([StringTable('080404B0', [
      StringStruct('FileDescription', '撤销解压 UndoExtract'),
      StringStruct('ProductName', 'UndoExtract'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('ProductVersion', '{ver}'),
      StringStruct('InternalName', 'UndoExtract'),
      StringStruct('OriginalFilename', 'UndoExtract.exe')])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""


def main():
    missing = [f for f in BUNDLED if not os.path.isfile(os.path.join(SEVEN_ZIP, f))]
    if missing:
        sys.exit(f"需要先安装 64 位 7-Zip，{SEVEN_ZIP} 下缺少：{', '.join(missing)}")
    dist, work = os.path.join(ROOT, "dist"), os.path.join(ROOT, "build")
    exe = os.path.join(dist, NAME + ".exe")
    if os.path.exists(exe):
        try:
            open(exe, "r+b").close()  # 正在运行的 exe 无法以写方式打开，借此检测
        except OSError:
            sys.exit(f"{exe} 正在运行，请先关闭它再打包。")

    if not os.path.isfile(VENV_PY):
        venv.create(os.path.join(ROOT, ".venv"), with_pip=True)
    subprocess.run([VENV_PY, "-m", "pip", "install", "-q", "--disable-pip-version-check", "pyinstaller"], check=True)

    version = re.search(r'^__version__ = "([\d.]+)"', open(SCRIPT, encoding="utf-8").read(), re.M).group(1)
    nums = tuple(int(x) for x in version.split(".")) + (0,) * (4 - version.count(".") - 1)
    os.makedirs(work, exist_ok=True)
    version_file = os.path.join(work, "version_info.txt")
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(VERSION_INFO.format(tup=nums, ver=version))

    cmd = [VENV_PY, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
           "--name", NAME, "--icon", os.path.join(ROOT, "icon.ico"), "--version-file", version_file,
           "--distpath", dist, "--workpath", work, "--specpath", work]
    for f in BUNDLED:
        cmd += ["--add-data", os.path.join(SEVEN_ZIP, f) + os.pathsep + "7zip"]
    cmd += ["--add-data", os.path.join(ROOT, "icon.ico") + os.pathsep + "."]
    cmd.append(SCRIPT)
    subprocess.run(cmd, check=True, cwd=ROOT)

    # 7-Zip 以 LGPL 授权分发，许可证随 exe 一起放出
    shutil.copy(os.path.join(SEVEN_ZIP, "License.txt"), os.path.join(dist, "7-Zip License.txt"))
    with open(exe, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    print(f"\n完成：{exe}\nSHA-256：{sha256}")


if __name__ == "__main__":
    main()
