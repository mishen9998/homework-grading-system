"""Tk desktop panel. UI remains on its main thread; lifecycle work is queued."""
import argparse
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from .core import AssistantError, Controller, InstanceLock, LOCAL, ROOT


class DesktopApp:
    def __init__(self, window, auto_start=True, auto_open=True):
        self.window = window
        self.events = queue.Queue()
        self.controller = Controller(lambda text: self.events.put(('message', text)))
        self.busy = False
        self.closing = False
        self.checking = False
        self.healthy = False
        self.next_check = 0
        self.auto_open = tk.BooleanVar(value=auto_open)
        self.status = tk.StringVar(value='尚未启动')
        self.detail = tk.StringVar(value='正在准备本机运行环境。')
        window.title('作业管理系统 · 桌面助手')
        window.geometry('820x580')
        window.minsize(760, 540)
        window.configure(bg='#eef3f9')
        style = ttk.Style(window)
        style.theme_use('clam')
        style.configure('TFrame', background='#eef3f9')
        style.configure('TLabel', background='#eef3f9', foreground='#23334a', font=('Microsoft YaHei UI', 10))
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 23, 'bold'))
        style.configure('Status.TLabel', font=('Microsoft YaHei UI', 16, 'bold'), foreground='#2563eb')
        style.configure('TButton', font=('Microsoft YaHei UI', 10), padding=(14, 10))
        style.configure('Primary.TButton', background='#2563eb', foreground='white')
        style.map('Primary.TButton', background=[('active', '#1d4ed8'), ('disabled', '#cbd5e1')])
        body = ttk.Frame(window, padding=28)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='作业管理系统', style='Title.TLabel').pack(anchor='w')
        ttk.Label(body, text='桌面运行助手  /  本机模式 · 数据保留 · 无需重复配置').pack(anchor='w', pady=(6, 24))
        ttk.Label(body, textvariable=self.status, style='Status.TLabel').pack(anchor='w')
        ttk.Label(body, textvariable=self.detail, wraplength=740).pack(anchor='w', pady=(8, 12))
        ttk.Label(body, text='访问地址：' + self.controller.url).pack(anchor='w')
        controls = ttk.Frame(body)
        controls.pack(fill='x', pady=20)
        self.start_button = ttk.Button(controls, text='一键启动', style='Primary.TButton', command=self.start)
        self.start_button.pack(side='left', padx=(0, 10))
        self.open_button = ttk.Button(controls, text='打开系统', command=self.open_system, state='disabled')
        self.open_button.pack(side='left', padx=(0, 10))
        self.stop_button = ttk.Button(controls, text='安全停止', command=self.stop, state='disabled')
        self.stop_button.pack(side='left')
        ttk.Checkbutton(body, text='启动就绪后自动打开系统', variable=self.auto_open).pack(anchor='w')
        ttk.Label(body, text='运行记录').pack(anchor='w', pady=(18, 6))
        self.messages = tk.Text(body, height=6, relief='flat', bg='white', fg='#475569',
                                font=('Microsoft YaHei UI', 10), padx=12, pady=8, state='disabled', wrap='word')
        self.messages.pack(fill='both', expand=True)
        footer = ttk.Frame(body)
        footer.pack(fill='x', pady=(16, 0))
        ttk.Button(footer, text='查看日志', command=lambda: self.open_path(LOCAL)).pack(side='left')
        ttk.Button(footer, text='使用说明', command=lambda: self.open_path(ROOT / '桌面助手使用说明.md')).pack(side='left', padx=8)
        ttk.Button(footer, text='数据库迁移指南', command=lambda: self.open_path(ROOT / '数据库/数据库迁移指南.md')).pack(side='left')
        self.append('助手不自动启动外部 AI worker，不修改数据库或结束其他程序。')
        window.protocol('WM_DELETE_WINDOW', self.close)
        window.after(150, self.pump)
        if auto_start:
            window.after(300, self.start)

    def append(self, text):
        self.messages.configure(state='normal')
        self.messages.insert('end', time.strftime('%H:%M:%S') + '  ' + text + '\n')
        if int(self.messages.index('end-1c').split('.')[0]) > 150:
            self.messages.delete('1.0', '30.0')
        self.messages.see('end')
        self.messages.configure(state='disabled')

    def open_path(self, path):
        try:
            os.startfile(str(path))
        except OSError:
            messagebox.showerror('无法打开', '请手动打开：' + str(path), parent=self.window)

    def open_system(self):
        if self.healthy:
            webbrowser.open(self.controller.url)

    def run_operation(self, operation):
        if self.busy:
            return
        self.busy = True
        self.healthy = False
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='disabled')
        self.open_button.configure(state='disabled')
        self.status.set('正在启动…' if operation == 'start' else '正在安全停止…')

        def work():
            try:
                getattr(self.controller, operation)()
                self.events.put((operation, None))
            except AssistantError as exc:
                self.events.put(('error', str(exc)))
            except Exception as exc:
                self.events.put(('error', f'操作未完成（{type(exc).__name__}），请查看日志和使用说明。'))
        threading.Thread(target=work, daemon=True).start()

    def start(self):
        self.run_operation('start')

    def stop(self):
        self.run_operation('stop')

    def close(self):
        if self.busy:
            messagebox.showinfo('操作进行中', '请等待本次启动或停止完成。', parent=self.window)
            return
        if self.controller.alive():
            if not messagebox.askyesno('退出助手', '退出将停止本助手启动的服务。\n请确认当前没有师生正在使用。是否安全停止并退出？', parent=self.window):
                return
            self.closing = True
            self.stop()
        else:
            self.window.destroy()

    def pump(self):
        while not self.events.empty():
            kind, text = self.events.get_nowait()
            if kind == 'message':
                self.detail.set(text)
                self.append(text)
                continue
            if kind == 'health':
                self.checking = False
                if self.busy:
                    continue
                self.healthy = bool(text)
                if not self.healthy:
                    self.status.set('服务需要检查')
                    self.detail.set('连接未就绪或进程已停止，请查看日志；助手不会无限重启。')
                else:
                    self.status.set('运行正常')
                    self.detail.set('数据库已连接。关闭浏览器不影响服务；请用“安全停止”结束运行。')
            else:
                self.busy = False
                self.healthy = kind == 'start'
                if kind == 'error':
                    self.closing = False
                    self.status.set('需要处理')
                    self.detail.set(text)
                    self.append(text)
                elif kind == 'start':
                    self.status.set('运行正常')
                    self.detail.set('数据库已连接。关闭浏览器不影响服务；请用“安全停止”结束运行。')
                    if self.auto_open.get():
                        self.open_system()
                elif kind == 'stop':
                    self.status.set('已安全停止')
                    self.detail.set('账号、作业和附件均保留，可随时再次启动。')
                    self.append('本助手创建的服务已停止。')
                    if self.closing:
                        self.window.destroy()
                        return
            self.start_button.configure(state='disabled' if self.controller.alive() else 'normal')
            self.stop_button.configure(state='normal' if self.controller.alive() else 'disabled')
            self.open_button.configure(state='normal' if self.healthy else 'disabled')
        if not self.busy and self.controller.process and not self.checking and time.monotonic() >= self.next_check:
            self.checking = True
            self.next_check = time.monotonic() + 5
            threading.Thread(target=lambda: self.events.put(('health', self.controller.ready())), daemon=True).start()
        self.window.after(150, self.pump)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-auto-start', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    window = tk.Tk()
    window.withdraw()
    try:
        lock = InstanceLock(LOCAL / 'assistant.lock')
    except AssistantError as exc:
        messagebox.showinfo('桌面助手', str(exc), parent=window)
        window.destroy()
        return
    try:
        DesktopApp(window, auto_start=not args.no_auto_start, auto_open=not args.no_browser)
        window.deiconify()
        window.mainloop()
    finally:
        lock.close()


if __name__ == '__main__':
    main()
