"""撤销解压 UndoExtract：读取原压缩包的文件清单，找出散落在文件夹里的解压文件并删除。

用法：运行后把压缩包拖进窗口（或点“选择…”），也可以 `pyw undo_extract.pyw 压缩包路径`。
"""
import ctypes
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import tkinter as tk
import zlib
from ctypes import wintypes
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

__version__ = "1.1.0"

TAR_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tbz", ".tar.xz", ".txz", ".tar.zst", ".tzst")

MATCH, OVERWRITTEN, DIFF, MISSING = "match", "overwritten", "diff", "missing"
STATUS_ORDER = {MATCH: 0, OVERWRITTEN: 1, DIFF: 2, MISSING: 3}

kernel32, user32, shell32 = ctypes.windll.kernel32, ctypes.windll.user32, ctypes.windll.shell32

# ---------------------------------------------------------------- 界面文字

STRINGS = {
    "zh": {
        "app": "撤销解压 UndoExtract",
        "archive": "压缩包",
        "target": "解压位置",
        "browse": "选择…",
        "password": "密码",
        "crc": "校验 CRC",
        "recycle": "删除到回收站",
        "scan": "扫描",
        "col_check": "删除",
        "col_status": "状态",
        "col_size": "大小",
        "col_path": "路径",
        "hint": "拖入压缩包开始扫描，拖入文件夹更改解压位置。",
        "select_matches": "选中一致项",
        "select_none": "全不选",
        "delete": "删除选中",
        "match": "一致",
        "match_size": "一致（仅大小）",
        "renamed": "改名的副本",
        "overwritten": "覆盖了原文件",
        "size": "大小不同",
        "content": "内容不同",
        "mtime": "时间不同",
        "missing": "不存在",
        "summary": "一致 {match} · 覆盖 {overwritten} · 不同 {diff} · 不存在 {missing}　｜　已选 {n} 个，{size}",
        "reading": "读取压缩包…",
        "verifying": "校验 {n}/{total}：{rel}",
        "deleting": "正在删除…",
        "error": "出错",
        "pick_archive": "选择压缩包",
        "pick_target": "选择解压位置",
        "archives": "压缩包",
        "all_files": "所有文件",
        "archive_not_found": "压缩包不存在。",
        "target_not_found": "解压位置不存在。",
        "nothing_found": "此位置没有压缩包中的文件，请检查解压位置。",
        "overwrite_warning": ("{n} 个文件（红色）在解压时覆盖了同名原文件，原内容无法由本工具恢复，"
                              "可尝试 右键 → 属性 → 以前的版本。\n\n这些文件默认不选中。"),
        "confirm_title": "确认删除",
        "confirm_recycle": "将 {n} 个文件（{size}）移到回收站，并移除变空的文件夹。",
        "confirm_permanent": "将永久删除 {n} 个文件（{size}），并移除变空的文件夹。此操作无法撤销。",
        "warn_diff": "⚠ 其中 {n} 个与压缩包内容不一致。",
        "warn_overwritten": "⚠ 其中 {n} 个覆盖了原文件，删除后该位置将没有文件。",
        "deleted": "已删除 {files} 个文件、{dirs} 个文件夹。",
        "deleted_recycle": "可在回收站中还原。",
        "partial_failure": "以下项目失败：",
        "err_recycle": "回收站操作失败，错误码 {code}",
        "err_remove": "{path}：{reason}",
        "err_7z_read": "无法读取压缩包（如已加密，请填写密码）：\n\n{detail}",
        "err_7z_parse": "无法解析 7-Zip 的输出。",
        "err_no_7z": "未找到 7-Zip，请先安装：https://www.7-zip.org",
    },
    "en": {
        "app": "UndoExtract",
        "archive": "Archive",
        "target": "Location",
        "browse": "Browse…",
        "password": "Password",
        "crc": "Verify CRC",
        "recycle": "Use Recycle Bin",
        "scan": "Scan",
        "col_check": "Delete",
        "col_status": "Status",
        "col_size": "Size",
        "col_path": "Path",
        "hint": "Drop an archive to scan. Drop a folder to change the location.",
        "select_matches": "Select matches",
        "select_none": "Select none",
        "delete": "Delete selected",
        "match": "Match",
        "match_size": "Match (size only)",
        "renamed": "Renamed copy",
        "overwritten": "Overwrote original",
        "size": "Size differs",
        "content": "Content differs",
        "mtime": "Time differs",
        "missing": "Missing",
        "summary": "Match {match} · Overwritten {overwritten} · Differs {diff} · Missing {missing}   |   "
                   "{n} selected, {size}",
        "reading": "Reading archive…",
        "verifying": "Verifying {n}/{total}: {rel}",
        "deleting": "Deleting…",
        "error": "Error",
        "pick_archive": "Choose archive",
        "pick_target": "Choose extraction location",
        "archives": "Archives",
        "all_files": "All files",
        "archive_not_found": "Archive not found.",
        "target_not_found": "Location not found.",
        "nothing_found": "No files from the archive were found here. Check the location.",
        "overwrite_warning": ("{n} file(s) (red) overwrote existing files during extraction. Their original contents "
                              "can't be recovered by this tool; try right-click → Properties → Previous Versions.\n\n"
                              "They are not selected by default."),
        "confirm_title": "Confirm delete",
        "confirm_recycle": "Move {n} file(s) ({size}) to the Recycle Bin and remove empty folders?",
        "confirm_permanent": "Permanently delete {n} file(s) ({size}) and remove empty folders? This cannot be undone.",
        "warn_diff": "⚠ {n} differ from the archive.",
        "warn_overwritten": "⚠ {n} overwrote original files; nothing will remain at those paths.",
        "deleted": "Deleted {files} file(s) and {dirs} folder(s).",
        "deleted_recycle": "They can be restored from the Recycle Bin.",
        "partial_failure": "Failed:",
        "err_recycle": "Recycle Bin operation failed, code {code}",
        "err_remove": "{path}: {reason}",
        "err_7z_read": "Can't read the archive (enter the password if it's encrypted):\n\n{detail}",
        "err_7z_parse": "Can't parse 7-Zip's output.",
        "err_no_7z": "7-Zip not found. Install it from https://www.7-zip.org",
    },
}
LANGUAGES = (("zh", "中文"), ("en", "English"))
SETTINGS_FILE = os.path.join(os.environ.get("APPDATA", ""), "UndoExtract", "settings.json")
lang = "zh"


def t(key, **kw):
    return STRINGS[lang][key].format(**kw)


def default_language():
    """上次选过的语言优先，否则跟随系统界面语言（中文系统用中文，其余用英文）。"""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            saved = json.load(f).get("lang")
        if saved in STRINGS:
            return saved
    except (OSError, ValueError, AttributeError):
        pass
    LANG_CHINESE = 0x04
    return "zh" if kernel32.GetUserDefaultUILanguage() & 0x3FF == LANG_CHINESE else "en"


def save_language(code):
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"lang": code}, f)
    except OSError:
        pass


class AppError(Exception):
    """带界面文字键的错误，显示时再按当前语言翻译。"""

    def __init__(self, key, **kw):
        super().__init__(key)
        self.key, self.kw = key, kw

    def __str__(self):
        return t(self.key, **self.kw)


@dataclass
class Entry:
    path: str  # 压缩包内的原始路径
    is_dir: bool
    size: int | None
    crc: int | None
    mtime: float | None = None  # 仅 tar 提供，用来弥补没有 CRC
    has_ctime: bool = False  # 压缩包里存了创建时间（解压时会被还原，无法据此判断覆盖）


@dataclass
class Item:
    rel: str
    full: str
    status: str
    reason: str  # STRINGS 里的键，显示时翻译
    size: int


def resource_path(*parts):
    """打包成 exe 时资源在 PyInstaller 的解压目录（sys._MEIPASS），否则在脚本旁边。"""
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), *parts)


# ---------------------------------------------------------------- 读取清单

def find_7z():
    # 优先用 exe 自带的 7-Zip，免得系统里的旧版本不支持所需参数
    candidates = [resource_path("7zip", "7z.exe"), shutil.which("7z")]
    candidates += [os.path.join(os.environ[v], "7-Zip", "7z.exe")
                   for v in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)") if v in os.environ]
    return next((p for p in candidates if p and os.path.isfile(p)), None)


def normalize(path):
    """把压缩包内路径转成安全的相对路径；含 .. 或绝对路径的条目返回 None。"""
    parts = [p for p in path.replace("\\", "/").split("/") if p not in ("", ".")]
    # 盘符、以及 Windows 文件名里不可能有的冒号（会被当成 NTFS 数据流）都不接受
    if not parts or ".." in parts or any(":" in p for p in parts):
        return None
    return os.path.join(*parts)


def list_with_7z(exe, archive, password):
    cmd = [exe, "l", "-slt", "-sccUTF-8"]
    if password:
        cmd.append("-p" + password)
    cmd += ["--", archive]  # 防止以 - 开头的文件名被当成参数
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    out = r.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    if r.returncode > 1:  # 1 是警告（如压缩包尾部有多余数据），清单仍然可用
        err = r.stderr.decode("utf-8", "replace").strip() or out.strip()
        raise AppError("err_7z_read", detail=err[-800:])
    _, sep, body = out.partition("\n----------\n")
    if not sep:
        raise AppError("err_7z_parse")
    entries = []
    for block in body.split("\n\n"):
        fields = dict(line.split(" = ", 1) for line in block.split("\n") if " = " in line)
        if "Path" not in fields:
            continue
        size, crc = fields.get("Size", ""), fields.get("CRC", "")
        entries.append(Entry(
            fields["Path"],
            is_dir=fields.get("Folder") == "+" or "D" in fields.get("Attributes", "").split(" ")[0],
            size=int(size) if size.isdigit() else None,
            crc=int(crc, 16) if crc else None,
            has_ctime=bool(fields.get("Created")),
        ))
    return entries


def list_with_tarfile(archive):
    # 7-Zip 对 .tar.gz 这类只能列出里面的 .tar，所以 tar 系列用标准库读取
    with tarfile.open(archive, "r:*") as tf:
        return [Entry(m.name, m.isdir(), m.size if m.isreg() else None, None, m.mtime)
                for m in tf.getmembers() if m.isdir() or m.isreg()]


def list_archive(archive, password=""):
    if archive.lower().endswith(TAR_SUFFIXES):
        return list_with_tarfile(archive)
    if exe := find_7z():
        return list_with_7z(exe, archive, password)
    raise AppError("err_no_7z")


# ---------------------------------------------------------------- 比对

def file_crc(path):
    crc = 0
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            crc = zlib.crc32(chunk, crc)
    return crc


def scan(archive, target, password="", use_crc=True, progress=lambda key, **kw: None):
    """返回 (items, dirs)：每个文件条目的比对结果，以及压缩包涉及的所有相对目录。"""
    progress("reading")
    files, dirs = {}, set()
    for e in list_archive(archive, password):
        rel = normalize(e.path)
        if rel is None:
            continue
        if e.is_dir:
            dirs.add(rel)
            continue
        files[rel] = e
        parent = os.path.dirname(rel)
        while parent:
            dirs.add(parent)
            parent = os.path.dirname(parent)

    archive_key = os.path.normcase(os.path.abspath(archive))
    items, last_report = [], 0.0
    for n, (rel, e) in enumerate(sorted(files.items()), 1):
        full = os.path.join(target, rel)
        if os.path.normcase(os.path.abspath(full)) == archive_key:
            continue  # 绝不删除压缩包自身
        if not os.path.isfile(full):
            items.append(Item(rel, full, MISSING, "missing", e.size or 0))
            continue
        size = os.path.getsize(full)
        if e.size is not None and size != e.size:
            status, reason = DIFF, "size"
        elif e.crc is not None and use_crc:
            if time.monotonic() - last_report > 0.1:  # 文件很多时限制刷新频率，免得界面卡住
                last_report = time.monotonic()
                progress("verifying", n=n, total=len(files), rel=rel)
            status, reason = (MATCH, "match") if file_crc(full) == e.crc else (DIFF, "content")
        elif e.mtime is not None and abs(os.path.getmtime(full) - e.mtime) > 2:
            status, reason = DIFF, "mtime"  # 没有 CRC 时防止误删同大小但改过的文件
        else:
            status, reason = MATCH, "match_size"
        items.append(Item(rel, full, status, reason, size))
    mark_overwritten(items, files, archive)
    items += find_renamed_copies(items, files, target, archive, use_crc)
    items.sort(key=lambda i: (STATUS_ORDER[i.status], i.rel.lower()))
    return items, dirs


class FILE_BASIC_INFO(ctypes.Structure):
    _fields_ = [
        ("CreationTime", ctypes.c_int64),
        ("LastAccessTime", ctypes.c_int64),
        ("LastWriteTime", ctypes.c_int64),
        ("ChangeTime", ctypes.c_int64),
        ("FileAttributes", wintypes.DWORD),
    ]


kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def file_times(path):
    """返回 NTFS 的 (创建时间, 变更时间)，单位秒。变更时间在每次写入或改属性时更新，os.stat 拿不到。"""
    FILE_READ_ATTRIBUTES, SHARE_ALL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS = 0x80, 7, 3, 0x02000000
    h = kernel32.CreateFileW(path, FILE_READ_ATTRIBUTES, SHARE_ALL, None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None)
    if h in (None, wintypes.HANDLE(-1).value):
        raise ctypes.WinError()
    try:
        info = FILE_BASIC_INFO()
        if not kernel32.GetFileInformationByHandleEx(h, 0, ctypes.byref(info), ctypes.sizeof(info)):  # FileBasicInfo
            raise ctypes.WinError()
    finally:
        kernel32.CloseHandle(h)
    return info.CreationTime / 1e7, info.ChangeTime / 1e7


def mark_overwritten(items, entries, archive, slack=60):
    """找出解压时覆盖了原有同名文件的条目。

    覆盖写入不会改变文件的创建时间，却会更新变更时间：被覆盖的文件创建时间远早于变更时间，
    新解出的文件两者都在解压那一刻。为排除“同一个包解压了两次”，还要求创建时间早于压缩包
    出现在磁盘上的时间；若压缩包是解压之后才重新下载的（比文件的变更时间还新），这一条无从判断，跳过。
    压缩包里存了创建时间的条目，解压时会被还原，无法判断，也跳过。
    """
    try:
        archive_birth, _ = file_times(archive)
    except OSError:
        return
    for i in items:
        if i.status != MATCH or entries[i.rel].has_ctime:
            continue
        try:
            birth, change = file_times(i.full)
        except OSError:
            continue
        if change - birth > slack and (birth < archive_birth - 2 or archive_birth > change):
            i.status, i.reason = OVERWRITTEN, "overwritten"


# 解压时遇到重名、选择“自动重命名”后生成的名字：7-Zip 为 a_1.txt，WinRAR 为 a(1).txt，资源管理器等为 a (1).txt
RENAME_SUFFIX = r"(?:_\d+|\(\d+\)| \(\d+\))"


def find_renamed_copies(items, entries, target, archive, use_crc):
    """找出解压时因重名被自动改名的副本，返回新的条目。

    只在原名位置已有文件（发生过重名）时查找；副本内容必须与压缩包一致（CRC，没有 CRC 时比修改时间），
    并且是压缩包出现之后才创建的，避免把以前留下的同名副本算进来（判断方式同 mark_overwritten）。
    """
    if not use_crc:
        return []  # 改名副本只靠内容认定，关闭校验时不找
    try:
        archive_birth, _ = file_times(archive)
    except OSError:
        return []
    # 压缩包里本来就有的名字：自身比对一致就不是副本；不一致时可能是别的文件改名占了它的位置
    by_path = {os.path.normcase(i.rel): i for i in items}
    listings, found = {}, []
    for item in items:
        if item.status == MISSING:
            continue
        e = entries[item.rel]
        parent, name = os.path.split(item.rel)
        stem, ext = os.path.splitext(name)
        pattern = re.compile(re.escape(stem) + RENAME_SUFFIX + re.escape(ext), re.IGNORECASE)
        if parent not in listings:
            try:
                listings[parent] = os.listdir(os.path.join(target, parent))
            except OSError:
                listings[parent] = []
        for candidate in listings[parent]:
            rel = os.path.join(parent, candidate)
            full = os.path.join(target, rel)
            existing = by_path.get(os.path.normcase(rel))
            if not pattern.fullmatch(candidate) or (existing and existing.status != DIFF) or not os.path.isfile(full):
                continue
            if os.path.getsize(full) != e.size:
                continue
            if e.crc is not None:
                same = file_crc(full) == e.crc
            elif e.mtime is not None:
                same = abs(os.path.getmtime(full) - e.mtime) <= 2
            else:
                continue  # 只能比大小时不认，免得误删
            try:
                birth, change = file_times(full)
            except OSError:
                continue
            if same and (birth >= archive_birth - 2 or archive_birth > change):
                if existing:
                    existing.status, existing.reason = MATCH, "renamed"
                else:
                    found.append(Item(rel, full, MATCH, "renamed", e.size))
    return found


# ---------------------------------------------------------------- 删除

class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", ctypes.c_void_p),
        ("pTo", ctypes.c_void_p),
        ("fFlags", ctypes.c_uint16),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def recycle(paths):
    """一次性把多个文件移到回收站，返回 0 表示成功。"""
    FO_DELETE = 3
    FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 0x4, 0x10, 0x40, 0x400
    buf = ctypes.create_unicode_buffer("\0".join(os.path.abspath(p) for p in paths) + "\0")
    op = SHFILEOPSTRUCTW(wFunc=FO_DELETE, pFrom=ctypes.addressof(buf),
                         fFlags=FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI)
    return shell32.SHFileOperationW(ctypes.byref(op))


def remove_files(items, dirs, target, to_recycle=True):
    """删除文件后，再从深到浅移除压缩包带来的、已经变空的文件夹。

    返回 (删掉的文件数, 删掉的文件夹数, 错误列表)，错误是待翻译的 AppError。
    """
    errors = []
    paths = [i.full for i in items]
    if to_recycle:
        for start in range(0, len(paths), 500):
            if code := recycle(paths[start:start + 500]):
                errors.append(AppError("err_recycle", code=f"0x{code:X}"))
    else:
        for p in paths:
            try:
                os.remove(p)
            except OSError as e:
                errors.append(AppError("err_remove", path=p, reason=e.strerror))
    removed = sum(not os.path.exists(p) for p in paths)

    removed_dirs = 0
    for rel in sorted(dirs, key=lambda d: d.count(os.sep), reverse=True):
        full = os.path.join(target, rel)
        try:
            is_link = os.path.islink(full) or getattr(os.path, "isjunction", lambda _: False)(full)
            if os.path.isdir(full) and not is_link and not os.listdir(full):
                os.rmdir(full)
                removed_dirs += 1
        except OSError:
            pass
    return removed, removed_dirs, errors


# ---------------------------------------------------------------- 拖放

WNDPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


def enable_file_drop(root, on_drop):
    """让 Tk 窗口接收从资源管理器拖进来的文件（Win32 WM_DROPFILES，无需第三方库）。

    on_drop 在 Tk 事件循环内部被调用，不能直接操作 tkinter，只应把数据转交出去。
    """
    WM_DROPFILES, GWLP_WNDPROC = 0x0233, -4
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallWindowProcW.restype = wintypes.LPARAM
    shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
    shell32.DragQueryFileW.argtypes = [wintypes.WPARAM, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    shell32.DragQueryFileW.restype = wintypes.UINT
    shell32.DragFinish.argtypes = [wintypes.WPARAM]

    root.update_idletasks()
    hwnd = user32.GetParent(root.winfo_id())  # Tk 的顶层框架窗口

    def wndproc(h, msg, wparam, lparam):
        if msg == WM_DROPFILES:
            paths = []
            for i in range(shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)):
                buf = ctypes.create_unicode_buffer(shell32.DragQueryFileW(wparam, i, None, 0) + 1)
                shell32.DragQueryFileW(wparam, i, buf, len(buf))
                paths.append(buf.value)
            shell32.DragFinish(wparam)
            on_drop(paths)
            return 0
        return user32.CallWindowProcW(old_proc, h, msg, wparam, lparam)

    root._drop_proc = WNDPROC(wndproc)  # 保持引用，避免被回收
    old_proc = user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.cast(root._drop_proc, ctypes.c_void_p))
    shell32.DragAcceptFiles(hwnd, True)


# ---------------------------------------------------------------- 界面

def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


COLUMNS = (  # (列, 标题键, 宽度, 对齐, 是否拉伸)
    ("check", "col_check", 56, "center", False),
    ("status", "col_status", 140, "w", False),
    ("size", "col_size", 90, "e", False),
    ("path", "col_path", 480, "w", True),
)


class App:
    def __init__(self, root, initial_archive=None):
        self.root = root
        self.archive = tk.StringVar()
        self.target = tk.StringVar()
        self.password = tk.StringVar()
        self.use_crc = tk.BooleanVar(value=True)
        self.use_recycle = tk.BooleanVar(value=True)
        self.lang = tk.StringVar(value=lang)
        self.items, self.dirs, self.checked = [], set(), set()
        self.scanned = None  # (archive, target)，删除时用
        self.warned_overwrite = None  # 已提示过覆盖的 (archive, target)，删除后重新扫描时不再弹窗
        self.busy = False
        self.events = queue.Queue()
        self.texts = []  # (控件, 文字键)，切换语言时统一刷新

        if os.path.isfile(icon := resource_path("icon.ico")):
            root.iconbitmap(default=icon)
        root.geometry("960x640")
        root.minsize(720, 420)
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont"):
            tkfont.nametofont(name).configure(family="Microsoft YaHei UI", size=9)
        line = tkfont.nametofont("TkDefaultFont").metrics("linespace")
        ttk.Style().configure("Treeview", rowheight=line + 8)

        frm = ttk.Frame(root, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(4, weight=1)

        langbar = ttk.Frame(frm)  # 语言切换放在右上角，一眼能看到
        langbar.grid(row=0, column=0, columnspan=3, sticky="e", pady=(0, 6))
        ttk.Label(langbar, text="语言 / Language").pack(side="left", padx=(0, 8))  # 双语固定文字，看不懂当前语言也能找到
        for code, name in LANGUAGES:
            ttk.Radiobutton(langbar, text=name, value=code, variable=self.lang, style="Toolbutton", width=9,
                            command=self.switch_language).pack(side="left")

        self.tr(ttk.Label(frm), "archive").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.archive).grid(row=1, column=1, sticky="ew", padx=8, pady=3)
        self.tr(ttk.Button(frm, command=self.pick_archive), "browse").grid(row=1, column=2)
        self.tr(ttk.Label(frm), "target").grid(row=2, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.target).grid(row=2, column=1, sticky="ew", padx=8, pady=3)
        self.tr(ttk.Button(frm, command=self.pick_target), "browse").grid(row=2, column=2)

        opts = ttk.Frame(frm)
        opts.grid(row=3, column=0, columnspan=3, sticky="ew", pady=8)
        self.tr(ttk.Label(opts), "password").pack(side="left")
        ttk.Entry(opts, textvariable=self.password, show="•", width=14).pack(side="left", padx=(6, 18))
        self.tr(ttk.Checkbutton(opts, variable=self.use_crc), "crc").pack(side="left")
        self.tr(ttk.Checkbutton(opts, variable=self.use_recycle), "recycle").pack(side="left", padx=18)
        self.scan_btn = self.tr(ttk.Button(opts, command=self.start_scan), "scan")
        self.scan_btn.pack(side="right")

        tf = ttk.Frame(frm)
        tf.grid(row=4, column=0, columnspan=3, sticky="nsew")
        tf.columnconfigure(0, weight=1)
        tf.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tf, columns=[c[0] for c in COLUMNS], show="headings")
        for col, _, width, anchor, stretch in COLUMNS:
            self.tree.column(col, width=width, anchor=anchor, stretch=stretch)
        for status, color in ((MATCH, "#1a7f37"), (OVERWRITTEN, "#c62828"), (DIFF, "#b35900"), (MISSING, "#8c8c8c")):
            self.tree.tag_configure(status, foreground=color)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<space>", lambda e: self.toggle(self.tree.selection()))

        bottom = ttk.Frame(frm)
        bottom.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        # 按钮先放，窗口变窄时被截断的是左边的状态文字而不是按钮
        self.delete_btn = self.tr(ttk.Button(bottom, command=self.confirm_delete, state="disabled"), "delete")
        self.delete_btn.pack(side="right")
        self.tr(ttk.Button(bottom, command=lambda: self.set_checked(set())), "select_none").pack(side="right", padx=6)
        self.tr(ttk.Button(bottom, command=self.check_matches), "select_matches").pack(side="right")
        self.status = ttk.Label(bottom)
        self.status.pack(side="left", fill="x", expand=True)

        self.apply_language()
        root.after(100, self.poll)
        try:
            enable_file_drop(root, lambda paths: self.events.put(("drop", None, paths)))
        except OSError:
            pass  # 拖放不可用时仍可点“选择…”
        if initial_archive:
            self.set_archive(initial_archive)

    # -------- 语言
    def tr(self, widget, key):
        """登记控件对应的文字键，返回控件本身。"""
        self.texts.append((widget, key))
        return widget

    def apply_language(self):
        self.root.title(f"{t('app')} {__version__}")
        for widget, key in self.texts:
            widget.configure(text=t(key))
        for col, key, _, anchor, _ in COLUMNS:
            self.tree.heading(col, text=t(key), anchor="center" if anchor == "center" else "w")
        for idx, item in enumerate(self.items):
            self.tree.set(str(idx), "status", t(item.reason))
        if self.scanned is None and not self.busy:
            self.status.configure(text=t("hint"))
        self.update_summary()

    def switch_language(self):
        global lang
        lang = self.lang.get()
        save_language(lang)
        self.apply_language()

    # -------- 输入
    def pick_archive(self):
        path = filedialog.askopenfilename(title=t("pick_archive"), filetypes=[
            (t("archives"), "*.zip *.7z *.rar *.tar *.gz *.tgz *.bz2 *.xz *.zst *.001 *.iso *.cab *.exe"),
            (t("all_files"), "*.*")])
        if path:
            self.set_archive(path)

    def set_archive(self, path):
        path = os.path.abspath(path)
        self.archive.set(path)
        self.target.set(os.path.dirname(path))
        self.start_scan()

    def set_target(self, path):
        self.target.set(os.path.abspath(path))
        if self.archive.get():
            self.start_scan()

    def pick_target(self):
        if path := filedialog.askdirectory(title=t("pick_target"), initialdir=self.target.get() or None):
            self.set_target(path)

    def on_drop(self, paths):
        """拖入文件当作压缩包；拖入文件夹当作解压文件夹。"""
        if self.busy:
            return
        if files := [p for p in paths if os.path.isfile(p)]:
            self.set_archive(files[0])
        elif folders := [p for p in paths if os.path.isdir(p)]:
            self.set_target(folders[0])

    # -------- 后台任务
    def run_bg(self, fn, on_done):
        self.busy = True
        self.scan_btn.configure(state="disabled")
        self.delete_btn.configure(state="disabled")

        def worker():
            try:
                self.events.put(("done", on_done, fn()))
            except Exception as e:  # noqa: BLE001 - 所有错误都要显示给用户
                self.events.put(("error", None, e))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, cb, payload = self.events.get_nowait()
                if kind == "progress":
                    key, kw = payload
                    self.status.configure(text=t(key, **kw))
                    continue
                if kind == "drop":
                    self.on_drop(payload)
                    continue
                self.busy = False
                self.scan_btn.configure(state="normal")
                if kind == "error":
                    self.status.configure(text=t("error"))
                    messagebox.showerror(t("app"), str(payload), parent=self.root)
                else:
                    cb(payload)
                self.update_summary()
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def start_scan(self):
        if self.busy:
            return
        archive, target = self.archive.get().strip().strip('"'), self.target.get().strip().strip('"')
        if not os.path.isfile(archive):
            messagebox.showwarning(t("app"), t("archive_not_found"), parent=self.root)
            return
        if not os.path.isdir(target):
            messagebox.showwarning(t("app"), t("target_not_found"), parent=self.root)
            return
        password, use_crc = self.password.get(), self.use_crc.get()
        progress = lambda key, **kw: self.events.put(("progress", None, (key, kw)))
        self.tree.delete(*self.tree.get_children())
        self.items, self.checked = [], set()
        self.run_bg(lambda: (archive, target, *scan(archive, target, password, use_crc, progress)),
                    self.show_results)

    def show_results(self, result):
        archive, target, self.items, self.dirs = result
        self.scanned = (archive, target)
        for idx, item in enumerate(self.items):
            self.tree.insert("", "end", iid=str(idx), tags=(item.status,),
                             values=("", t(item.reason), fmt_size(item.size), item.rel))
        self.check_matches()
        if self.items and all(i.status == MISSING for i in self.items):
            messagebox.showinfo(t("app"), t("nothing_found"), parent=self.root)
        overwritten = sum(i.status == OVERWRITTEN for i in self.items)
        if overwritten and self.warned_overwrite != self.scanned:
            self.warned_overwrite = self.scanned
            messagebox.showwarning(t("app"), t("overwrite_warning", n=overwritten), parent=self.root)

    # -------- 勾选
    def on_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "cell" and self.tree.identify_column(event.x) == "#1":
            if row := self.tree.identify_row(event.y):
                self.toggle((row,))
                return "break"

    def toggle(self, iids):
        new = set(self.checked)
        for iid in iids:
            if self.items[int(iid)].status != MISSING:
                new ^= {iid}
        self.set_checked(new)

    def check_matches(self):
        self.set_checked({str(i) for i, item in enumerate(self.items) if item.status == MATCH})

    def set_checked(self, checked):
        self.checked = checked
        for idx, item in enumerate(self.items):
            iid = str(idx)
            mark = "" if item.status == MISSING else ("☑" if iid in checked else "☐")
            if self.tree.set(iid, "check") != mark:
                self.tree.set(iid, "check", mark)
        self.update_summary()

    def update_summary(self):
        if self.busy or self.scanned is None:
            return
        counts = {s: sum(i.status == s for i in self.items) for s in STATUS_ORDER}
        chosen = [self.items[int(i)] for i in self.checked]
        self.status.configure(text=t("summary", **counts, n=len(chosen), size=fmt_size(sum(i.size for i in chosen))))
        self.delete_btn.configure(state="normal" if chosen else "disabled")

    # -------- 删除
    def confirm_delete(self):
        if self.busy or not self.checked:
            return
        chosen = [self.items[int(i)] for i in sorted(self.checked, key=int)]
        recycle_on = self.use_recycle.get()
        msg = t("confirm_recycle" if recycle_on else "confirm_permanent",
                n=len(chosen), size=fmt_size(sum(i.size for i in chosen)))
        if diff := sum(i.status == DIFF for i in chosen):
            msg += "\n\n" + t("warn_diff", n=diff)
        if overwritten := sum(i.status == OVERWRITTEN for i in chosen):
            msg += "\n\n" + t("warn_overwritten", n=overwritten)
        if not messagebox.askyesno(t("confirm_title"), msg, icon="warning", parent=self.root):
            return
        target, dirs = self.scanned[1], self.dirs
        self.status.configure(text=t("deleting"))
        self.run_bg(lambda: remove_files(chosen, dirs, target, recycle_on), self.after_delete)

    def after_delete(self, result):
        removed, removed_dirs, errors = result
        text = t("deleted", files=removed, dirs=removed_dirs)
        if self.use_recycle.get():
            text += "\n" + t("deleted_recycle")
        if errors:
            text += "\n\n" + t("partial_failure") + "\n" + "\n".join(str(e) for e in errors[:10])
        messagebox.showinfo(t("app"), text, parent=self.root)
        self.start_scan()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    global lang
    lang = default_language()
    root = tk.Tk()
    App(root, sys.argv[1] if len(sys.argv) > 1 else None)
    root.mainloop()


if __name__ == "__main__":
    main()
