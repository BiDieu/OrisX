#!/usr/bin/env python3
# OrisX

import os
import sys
import json
import subprocess
import threading
import socket
import time
import getpass
import shutil
from datetime import datetime
from pathlib import Path

#尝试导入Unix的模块（好像没有用）
try:
    import pwd
    import grp
    HAS_UNIX_MODULES = True
except ImportError:
    HAS_UNIX_MODULES = False

#五颜六色喵
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    BLACK = '\033[30m'
    DIM = '\033[2m'

class OrisXSystem:
    def __init__(self):
        #计时器启动喵
        self.boot_time = time.time()

        #系统信息配置喵
        self.system_name = "OrisX"
        self.kernel_version = "26.1-inside"
        self.arch = "py"
        self.current_user = None
        self.hostname = "orisx"
        self.current_dir = "/root"
        self.uid = 0
        self.gid = 0
        self.shell = "/bin/bash"
        self.term = "xterm-256color"
        self.logged_in = False

        # 文件系统根目录
        self.fs_root = os.path.abspath("./orisx_root")
        self.meta_file = os.path.join(self.fs_root, ".orisx_meta.json")

        #系统状态喵
        self.commands = {}
        self.running = True
        self.ssh_server = None
        self.ssh_port = 2222
        self.history = []
        self.users = {}
        self.env_vars = {}
        #系统用户の密码
        self.default_users = {
            "root": {"password": "root", "uid": 0, "gid": 0, "home": "/root", "shell": "/bin/bash", "gecos": "root"},
            "orisx": {"password": "orisx", "uid": 1000, "gid": 1000, "home": "/home/orisx", "shell": "/bin/bash", "gecos": "orisx"},
            "guest": {"password": "guest", "uid": 1001, "gid": 1001, "home": "/home/guest", "shell": "/bin/bash", "gecos": "guest"}
        }
        
        #初始化系统喵
        self.init_system()
        self.register_commands()
        self.show_login_prompt()
    
    def log_boot(self, message, level="INFO"):
        """启动信息记录喵"""
        elapsed = time.time() - self.boot_time
        timestamp = f"[{elapsed:14.6f}]"
        
        prefix = {
            "INFO": f"{Colors.CYAN}INFO{Colors.ENDC}",
            "OK": f"{Colors.GREEN}OK{Colors.ENDC}",
            "WARN": f"{Colors.YELLOW}WARNING{Colors.ENDC}",
            "ERR": f"{Colors.RED}ERROR{Colors.ENDC}"
        }.get(level, "INFO")
        
        print(f"{Colors.DIM}{timestamp}{Colors.ENDC} {prefix} {message}")
    
    def init_system(self):
        """文件系统初始化喵"""
        # ★ 关键修复：先设置默认用户
        self.users = self.default_users.copy()
        
        #创建根目录喵
        if not os.path.exists(self.fs_root):
            os.makedirs(self.fs_root)
            self.log_boot(f"Creating filesystem root: {self.fs_root}", "OK")
            self.create_filesystem()
        else:
            self.log_boot(f"Using existing filesystem: {self.fs_root}", "OK")
            #加载用户数据（会合并 JSON 中的用户）
            self.load_users()
        
        #看看用户目录是否存在喵
        for username, user in self.users.items():
            home_path = self._real_path(user["home"])
            if not os.path.exists(home_path):
                os.makedirs(home_path, exist_ok=True)
                self.log_boot(f"Created home directory: {user['home']}", "OK")
        
        self.log_boot(f"Kernel {self.kernel_version} on an {self.arch}", "INFO")
        self.log_boot("System ready", "OK")
    
    def _real_path(self, path):
        """变变变！（虚拟路径==>真实路径）"""
        if not path:
            path = "/"
        if path.startswith('/'):
            #在处理Windows上路径...
            if os.name == 'nt':
                #移除开头的/连接
                rel_path = path[1:] if path != '/' else ''
                return os.path.join(self.fs_root, rel_path.replace('/', os.sep))
            return os.path.join(self.fs_root, path[1:])
        return os.path.join(self.fs_root, path.replace('/', os.sep))
    
    def _virtual_path(self, real_path):
        """变回来（"""
        if real_path.startswith(self.fs_root):
            rel = os.path.relpath(real_path, self.fs_root)
            if rel == '.':
                return '/'
            return '/' + rel.replace(os.sep, '/')
        return real_path.replace(os.sep, '/')
    
    def _get_file_info(self, path):
        """得文件信息喵"""
        try:
            stat = os.stat(path)
            if HAS_UNIX_MODULES:
                try:
                    owner = pwd.getpwuid(stat.st_uid).pw_name
                except:
                    owner = str(stat.st_uid)
                try:
                    group = grp.getgrgid(stat.st_gid).gr_name
                except:
                    group = str(stat.st_gid)
            else:
                #Windows下使用用户名
                try:
                    import getpass
                    owner = getpass.getuser()
                except:
                    owner = "unknown"
                group = "unknown"
            
            return {
                'size': stat.st_size,
                'mode': oct(stat.st_mode)[-3:],
                'owner': owner,
                'group': group,
                'mtime': datetime.fromtimestamp(stat.st_mtime).strftime('%b %d %H:%M'),
                'is_dir': os.path.isdir(path)
            }
        except:
            return None
    
    def create_filesystem(self):
        """初始化真实文件系统结构喵"""
        # ★ 安全保护：如果 users 为空，从默认用户复制
        if not self.users:
            self.users = self.default_users.copy()
        
        #标准目录喵
        dirs = [
            "/etc", "/home", "/lib",
            "/root", "/tmp", 
        ]
        
        for d in dirs:
            real_path = self._real_path(d)
            os.makedirs(real_path, exist_ok=True)
            self.log_boot(f"Created directory: {d}", "OK")
        
        #用户主目录喵
        for user in self.users.values():
            home_path = self._real_path(user["home"])
            os.makedirs(home_path, exist_ok=True)
            
            #创建用户配置文件喵
            bashrc_path = os.path.join(home_path, ".bashrc")
            if not os.path.exists(bashrc_path):
                with open(bashrc_path, 'w', encoding='utf-8') as f:
                    f.write("# .bashrc\nPS1='\\u@\\h:\\w\\$ '\nalias ll='ls -alF'\nalias ls='ls --color=auto'\n")
            
            bash_profile_path = os.path.join(home_path, ".bash_profile")
            if not os.path.exists(bash_profile_path):
                with open(bash_profile_path, 'w', encoding='utf-8') as f:
                    f.write("# .bash_profile\nif [ -f ~/.bashrc ]; then\n  . ~/.bashrc\nfi\n")
        
        # /etc配置文件喵
        etc_path = self._real_path("/etc")
        etc_files = {
            "hostname": f"{self.hostname}\n",
            "hosts": "127.0.0.1 localhost localhost.localdomain\n::1 localhost localhost.localdomain\n",
            "fstab": "# /etc/fstab\n/dev/sda1 / ext4 defaults 1 1\n",
            "issue": "OrisX\nKernel \\r on an \\m\n",
            "os-release": f'NAME="{self.system_name}"\nVERSION="{self.kernel_version}"\nID="orisx"\nVERSION_ID="26.1"\nPRETTY_NAME="{self.system_name} {self.kernel_version}"\n',
            "bash.bashrc": "# /etc/bash.bashrc\nPS1='\\u@\\h:\\w\\$ '\nalias ls='ls --color=auto'\n"
        }
        
        for name, content in etc_files.items():
            file_path = os.path.join(etc_path, name)
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log_boot(f"Created /etc/{name}", "OK")
        
        # ★ 保存用户信息（现在 self.users 有数据了）
        self.save_users()
    
    def load_users(self):
        """加载用户数据喵 - 现在会读取密码了！"""
        # 先从默认用户开始
        self.users = self.default_users.copy()
        
        if os.path.exists(self.meta_file):
            try:
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    loaded_users = meta.get('users', {})
                    for username, user_data in loaded_users.items():
                        if username in self.users:
                            # 更新用户信息，包括密码！
                            self.users[username].update(user_data)
                        else:
                            # 新用户，确保有密码字段
                            if 'password' not in user_data:
                                user_data['password'] = 'password'
                            self.users[username] = user_data
                    self.hostname = meta.get('hostname', 'orisx')
                    self.log_boot("Loaded user data (including passwords)", "OK")
            except Exception as e:
                self.log_boot(f"Error loading user data: {e}", "WARN")
    
    def save_users(self):
        """保存用户数据喵 - 现在会保存密码了！"""
        try:
            users_to_save = {}
            for username, user_data in self.users.items():
                # 保存所有字段，包括密码！
                users_to_save[username] = user_data.copy()
            
            meta = {
                'hostname': self.hostname,
                'users': users_to_save,
                'last_modified': datetime.now().isoformat()
            }
            
            #确保目录存在喵
            os.makedirs(os.path.dirname(self.meta_file), exist_ok=True)
            
            with open(self.meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            self.log_boot(f"Error saving user data: {e}", "WARN")
    
    def show_login_prompt(self):
        """登录界面喵"""
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print(f"""
{Colors.GREEN}OrisX{Colors.ENDC}
{Colors.CYAN}Kernel {self.kernel_version}-{self.arch}{Colors.ENDC}

{Colors.YELLOW}{self.hostname} login: {Colors.ENDC}""", end='')
        
        while not self.logged_in:
            try:
                username = input().strip()
                if not username:
                    print(f"{Colors.YELLOW}{self.hostname} login: {Colors.ENDC}", end='')
                    continue
                
                if username in self.users:
                    password = getpass.getpass("Password: ")
                    
                    if password == self.users[username]["password"]:
                        self.login_user(username)
                        break
                    else:
                        print(f"{Colors.RED}Login incorrect{Colors.ENDC}")
                        print(f"{Colors.YELLOW}{self.hostname} login: {Colors.ENDC}", end='')
                else:
                    print(f"{Colors.RED}Login incorrect{Colors.ENDC}")
                    print(f"{Colors.YELLOW}{self.hostname} login: {Colors.ENDC}", end='')
                    
            except KeyboardInterrupt:
                print("\n")
                continue
            except EOFError:
                print()
                break
        
        if self.logged_in:
            print(f"Last login: {datetime.now().strftime('%a %b %d %H:%M:%S')} on tty1")
            print(f"\n{Colors.GREEN}Welcome to {self.system_name} {self.kernel_version}{Colors.ENDC}")
    
    def login_user(self, username):
        """用户登录喵"""
        user = self.users[username]
        self.current_user = username
        self.uid = user["uid"]
        self.gid = user["gid"]
        self.current_dir = user["home"]
        self.shell = user["shell"]
        self.logged_in = True
        
        #用户目录存在嘛（我不知道喵）
        home_path = self._real_path(self.current_dir)
        if not os.path.exists(home_path):
            os.makedirs(home_path, exist_ok=True)
        
        #设置环境变量（嗯）
        self.env_vars = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": self._real_path(user["home"]),
            "SHELL": user["shell"],
            "TERM": "xterm-256color",
            "USER": username,
            "LOGNAME": username,
            "PWD": self._real_path(self.current_dir),
            "LANG": "en_US.UTF-8"
        }
        
        #切换到用户目录
        try:
            os.chdir(self._real_path(self.current_dir))
        except:
            pass
    
    def switch_user(self, username):
        """切换用户喵"""
        if username in self.users:
            self.login_user(username)
            print(f"Switched to user: {username}")
        else:
            print(f"su: user {username} does not exist")
    
    def resolve_path(self, path):
        """路径解析喵"""
        if not path:
            return self.current_dir
        
        if path.startswith('/'):
            return path
        elif path.startswith('~'):
            return self.users[self.current_user]["home"] + path[1:]
        elif path == '.':
            return self.current_dir
        elif path == '..':
            parent = os.path.dirname(self.current_dir)
            return parent if parent else '/'
        else:
            if self.current_dir == '/':
                return '/' + path
            return self.current_dir + '/' + path
    
    def register_commands(self):
        """系统命令映射喵"""
        self.commands = {
            "help": self.cmd_help,
            "ls": self.cmd_ls,
            "ll": self.cmd_ls_long,
            "cd": self.cmd_cd,
            "pwd": self.cmd_pwd,
            "cat": self.cmd_cat,
            "echo": self.cmd_echo,
            "touch": self.cmd_touch,
            "mkdir": self.cmd_mkdir,
            "rm": self.cmd_rm,
            "rmdir": self.cmd_rmdir,
            "mv": self.cmd_mv,
            "cp": self.cmd_cp,
            "clear": self.cmd_clear,
            "history": self.cmd_history,
            "date": self.cmd_date,
            "whoami": self.cmd_whoami,
            "hostname": self.cmd_hostname,
            "uname": self.cmd_uname,
            "su": self.cmd_su,
            "exit": self.cmd_exit,
            "logout": self.cmd_logout,
            "reboot": self.cmd_reboot,
            "shutdown": self.cmd_shutdown,
            "sysinfo": self.cmd_sysinfo,
            "df": self.cmd_df,
            "du": self.cmd_du,
            "id": self.cmd_id,
            "who": self.cmd_who,
            "uptime": self.cmd_uptime,
            "free": self.cmd_free,
            "ps": self.cmd_ps,
            "kill": self.cmd_kill,
            "ssh": self.cmd_ssh,
            "ssh-start": self.cmd_ssh_start,
            "ssh-stop": self.cmd_ssh_stop,
            "tree": self.cmd_tree,
            "find": self.cmd_find,
            "grep": self.cmd_grep,
            "head": self.cmd_head,
            "tail": self.cmd_tail,
            "wc": self.cmd_wc,
            "sort": self.cmd_sort,
            "uniq": self.cmd_uniq,
            "env": self.cmd_env,
            "export": self.cmd_export,
            "edit": self.cmd_edit,
            "nano": self.cmd_edit,
            "vi": self.cmd_edit,
            "vim": self.cmd_edit,
            "passwd": self.cmd_passwd,
        }
    
    def get_prompt(self):
        """得命令提示符喵"""
        if not self.logged_in:
            return ""
        
        dir_name = self.current_dir
        if dir_name.startswith(self.users[self.current_user]["home"]):
            dir_name = '~' + dir_name[len(self.users[self.current_user]["home"]):]
        
        return f"{Colors.GREEN}{self.current_user}@{self.hostname}{Colors.ENDC}:{Colors.BLUE}{dir_name}{Colors.ENDC}$ "
    
    # ============ 命令 ============
    
    def cmd_passwd(self, args):
        """修改当前用户密码"""
        if args:
            username = args[0]
            if username not in self.users:
                print(f"passwd: user '{username}' does not exist")
                return
            if username != self.current_user and self.current_user != "root":
                print(f"passwd: only root can change other user's password")
                return
        else:
            username = self.current_user
        
        if username == self.current_user:
            old = getpass.getpass("Current password: ")
            if old != self.users[username]["password"]:
                print("passwd: incorrect password")
                return
        
        new = getpass.getpass("New password: ")
        confirm = getpass.getpass("Re-enter new password: ")
        
        if new != confirm:
            print("passwd: passwords do not match")
            return
        
        if len(new) < 1:
            print("passwd: password cannot be empty")
            return
        
        self.users[username]["password"] = new
        self.save_users()
        print(f"passwd: password updated successfully for user '{username}'")
    
    def cmd_su(self, args):
        """切换用户"""
        if not args:
            print("su: missing username")
            return
        
        username = args[0]
        self.switch_user(username)
    
    def cmd_logout(self, args):
        """登出"""
        if self.current_user == "root":
            print("logout")
        self.logged_in = False
        self.current_user = None
        self.show_login_prompt()
    
    def cmd_exit(self, args):
        """退出系统（"""
        if self.current_user != "root":
            self.cmd_logout(args)
        else:
            self.running = False
            print("logout")
    
    def cmd_help(self, args):
        """显示帮助信息（真的有人看嘛）"""
        print(f"""\
{Colors.BOLD}GNU bash, version 5.1.16(1)-release (x86_64-pc-linux-gnu){Colors.ENDC}
Type `help' to see this list.
Type `help name' to find out more about the function `name'.

{Colors.BOLD}File commands:{Colors.ENDC}
 ls          cd          pwd         cat         echo        touch
 mkdir       rm          rmdir       mv          cp          tree
 find        grep        head        tail        wc          sort
 uniq        edit        nano        vi          vim

{Colors.BOLD}System commands:{Colors.ENDC}
 date        whoami      hostname    uname       uptime      free
 df          du          id          who         ps          kill
 su          logout      passwd

{Colors.BOLD}Network commands:{Colors.ENDC}
 ssh         ssh-start   ssh-stop

{Colors.BOLD}Other commands:{Colors.ENDC}
 clear       history     help        exit        reboot      shutdown
 sysinfo     env         export
""")
    
    def cmd_ls(self, args):
        """ls是干嘛的（好难猜啊"""
        show_all = False
        long_format = False
        path = None
        
        for arg in args:
            if arg == '-a':
                show_all = True
            elif arg == '-l':
                long_format = True
            elif arg == '-la' or arg == '-al':
                show_all = True
                long_format = True
            elif not arg.startswith('-'):
                path = arg
        
        if path is None:
            path = self.current_dir
        
        abs_path = self.resolve_path(path)
        real_path = self._real_path(abs_path)
        
        if not os.path.exists(real_path):
            print(f"ls: cannot access '{path}': No such file or directory")
            return
        
        if not os.path.isdir(real_path):
            print(f"ls: '{path}': Not a directory")
            return
        
        try:
            items = os.listdir(real_path)
            
            if not show_all:
                items = [item for item in items if not item.startswith('.')]
            
            if long_format:
                total = 0
                for item in sorted(items):
                    item_real_path = os.path.join(real_path, item)
                    try:
                        info = self._get_file_info(item_real_path)
                        if info:
                            total += info['size']
                            ftype = 'd' if info['is_dir'] else '-'
                            mode = info['mode']
                            owner = info['owner']
                            group = info['group']
                            size = info['size']
                            mtime = info['mtime']
                            color = Colors.BLUE if info['is_dir'] else Colors.GREEN if 'x' in mode else Colors.ENDC
                            print(f"{ftype}{mode} {owner:8} {group:8} {size:8} {mtime} {color}{item}{Colors.ENDC}")
                    except:
                        continue
                print(f"total {total}")
            else:
                cols = 4
                items_sorted = sorted(items)
                for i, item in enumerate(items_sorted):
                    item_real_path = os.path.join(real_path, item)
                    if os.path.isdir(item_real_path):
                        print(f"{Colors.BLUE}{item}/{Colors.ENDC}", end='\t')
                    else:
                        print(item, end='\t')
                    if (i + 1) % cols == 0:
                        print()
                if len(items_sorted) % cols != 0:
                    print()
        except PermissionError:
            print(f"ls: cannot open directory '{path}': Permission denied")
        except Exception as e:
            print(f"ls: error: {e}")
    
    def cmd_ls_long(self, args):
        """详细列表"""
        self.cmd_ls(['-l'] + args)
    
    def cmd_cd(self, args):
        """切换目录"""
        if not args:
            self.current_dir = self.users[self.current_user]["home"]
            self.env_vars["PWD"] = self._real_path(self.current_dir)
            try:
                os.chdir(self._real_path(self.current_dir))
            except:
                pass
            return
        
        path = args[0]
        abs_path = self.resolve_path(path)
        real_path = self._real_path(abs_path)
        
        if not os.path.exists(real_path):
            print(f"cd: {path}: No such file or directory")
            return
        
        if not os.path.isdir(real_path):
            print(f"cd: {path}: Not a directory")
            return
        
        self.current_dir = abs_path
        self.env_vars["PWD"] = self._real_path(self.current_dir)
        try:
            os.chdir(real_path)
        except:
            pass
    
    def cmd_pwd(self, args):
        print(self.current_dir)
    
    def cmd_cat(self, args):
        if not args:
            print("cat: missing file operand")
            return
        
        for path in args:
            abs_path = self.resolve_path(path)
            real_path = self._real_path(abs_path)
            
            if not os.path.exists(real_path):
                print(f"cat: {path}: No such file or directory")
                continue
            
            if os.path.isdir(real_path):
                print(f"cat: {path}: Is a directory")
                continue
            
            try:
                with open(real_path, 'r', encoding='utf-8') as f:
                    print(f.read(), end='')
            except UnicodeDecodeError:
                try:
                    with open(real_path, 'rb') as f:
                        print(f.read().decode('utf-8', errors='ignore'), end='')
                except Exception as e:
                    print(f"cat: {path}: {e}")
            except Exception as e:
                print(f"cat: {path}: {e}")
    
    def cmd_echo(self, args):
        if not args:
            print()
            return
        
        text = ' '.join(args)
        
        if '>>' in text:
            parts = text.split('>>', 1)
            content = parts[0].strip()
            filepath = parts[1].strip()
            
            abs_path = self.resolve_path(filepath)
            real_path = self._real_path(abs_path)
            
            try:
                os.makedirs(os.path.dirname(real_path), exist_ok=True)
                with open(real_path, 'a', encoding='utf-8') as f:
                    f.write(content + '\n')
            except Exception as e:
                print(f"echo: {e}")
        elif '>' in text:
            parts = text.split('>', 1)
            content = parts[0].strip()
            filepath = parts[1].strip()
            
            abs_path = self.resolve_path(filepath)
            real_path = self._real_path(abs_path)
            
            try:
                os.makedirs(os.path.dirname(real_path), exist_ok=True)
                with open(real_path, 'w', encoding='utf-8') as f:
                    f.write(content + '\n')
            except Exception as e:
                print(f"echo: {e}")
        else:
            print(text)
    
    def cmd_touch(self, args):
        """创建空文件或更新文件时间喵"""
        if not args:
            print("touch: missing file operand")
            return
        
        for arg in args:
            abs_path = self.resolve_path(arg)
            real_path = self._real_path(abs_path)
            
            try:
                if os.path.exists(real_path):
                    os.utime(real_path, None)
                else:
                    os.makedirs(os.path.dirname(real_path), exist_ok=True)
                    with open(real_path, 'w') as f:
                        pass
            except Exception as e:
                print(f"touch: {arg}: {e}")
    
    def cmd_mkdir(self, args):
        if not args:
            print("mkdir: missing operand")
            return
        
        for arg in args:
            abs_path = self.resolve_path(arg)
            real_path = self._real_path(abs_path)
            
            try:
                os.makedirs(real_path, exist_ok=False)
            except FileExistsError:
                print(f"mkdir: cannot create directory '{arg}': File exists")
            except Exception as e:
                print(f"mkdir: {arg}: {e}")
    
    def cmd_rm(self, args):
        if not args:
            print("rm: missing operand")
            return
        
        recursive = False
        force = False
        paths = []
        
        for arg in args:
            if arg == '-r' or arg == '-rf' or arg == '-fr':
                recursive = True
                if 'f' in arg:
                    force = True
            elif arg == '-f':
                force = True
            else:
                paths.append(arg)
        
        for path in paths:
            abs_path = self.resolve_path(path)
            real_path = self._real_path(abs_path)
            
            if not os.path.exists(real_path):
                if not force:
                    print(f"rm: cannot remove '{path}': No such file or directory")
                continue
            
            try:
                if os.path.isdir(real_path):
                    if recursive:
                        shutil.rmtree(real_path)
                    else:
                        print(f"rm: cannot remove '{path}': Is a directory")
                else:
                    os.remove(real_path)
            except Exception as e:
                print(f"rm: {path}: {e}")
    
    def cmd_rmdir(self, args):
        """删除空目录"""
        if not args:
            print("rmdir: missing operand")
            return
        
        for arg in args:
            abs_path = self.resolve_path(arg)
            real_path = self._real_path(abs_path)
            
            if not os.path.exists(real_path):
                print(f"rmdir: failed to remove '{arg}': No such file or directory")
                continue
            
            try:
                os.rmdir(real_path)
            except OSError as e:
                print(f"rmdir: failed to remove '{arg}': {e}")
    
    def cmd_mv(self, args):
        if len(args) < 2:
            print("mv: missing file operand")
            return
        
        src = self.resolve_path(args[0])
        dst = self.resolve_path(args[1])
        src_real = self._real_path(src)
        dst_real = self._real_path(dst)
        
        if not os.path.exists(src_real):
            print(f"mv: cannot stat '{args[0]}': No such file or directory")
            return
        
        if os.path.isdir(dst_real):
            basename = os.path.basename(src)
            dst_real = os.path.join(dst_real, basename)
            dst = self._virtual_path(dst_real)
        
        try:
            shutil.move(src_real, dst_real)
        except Exception as e:
            print(f"mv: {e}")
    
    def cmd_cp(self, args):
        """复制文件"""
        if len(args) < 2:
            print("cp: missing file operand")
            return
        
        src = self.resolve_path(args[0])
        dst = self.resolve_path(args[1])
        src_real = self._real_path(src)
        dst_real = self._real_path(dst)
        
        if not os.path.exists(src_real):
            print(f"cp: cannot stat '{args[0]}': No such file or directory")
            return
        
        if os.path.isdir(src_real):
            print("cp: omitting directory")
            return
        
        if os.path.isdir(dst_real):
            basename = os.path.basename(src)
            dst_real = os.path.join(dst_real, basename)
            dst = self._virtual_path(dst_real)
        
        try:
            shutil.copy2(src_real, dst_real)
        except Exception as e:
            print(f"cp: {e}")
    
    def cmd_clear(self, args):
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def cmd_history(self, args):
        """显示 命 令 历 史"""
        if self.history:
            for i, cmd in enumerate(self.history[-50:], 1):
                print(f"{i:4}  {cmd}")
        else:
            print("No command history")
    
    def cmd_date(self, args):
        now = datetime.now()
        print(now.strftime('%a %b %d %H:%M:%S %Z %Y'))
    
    def cmd_whoami(self, args):
        print(self.current_user)
    
    def cmd_hostname(self, args):
        """显示或设置主机名"""
        if args:
            self.hostname = args[0]
            self.save_users()
        else:
            print(self.hostname)
    
    def cmd_uname(self, args):
        """系统信息"""
        if '-a' in args:
            print(f"OrisX {self.hostname} {self.kernel_version} #1 SMP PREEMPT_DYNAMIC Mon Jan 1 00:00:00 UTC 2024 {self.arch} GNU/Linux")
        elif '-r' in args:
            print(self.kernel_version)
        elif '-s' in args:
            print("OrisX")
        elif '-n' in args:
            print(self.hostname)
        elif '-m' in args:
            print(self.arch)
        else:
            print("OrisX")
    
    def cmd_sysinfo(self, args):
        """系统详细信息"""
        uptime = time.time() - self.boot_time
        
        print(f"""
{Colors.BOLD}System Information{Colors.ENDC}
{Colors.CYAN}═══════════════════════════════════════════════════════{Colors.ENDC}
{Colors.BOLD}OS:{Colors.ENDC} {self.system_name} {self.kernel_version}
{Colors.BOLD}Kernel:{Colors.ENDC} {self.kernel_version}
{Colors.BOLD}Architecture:{Colors.ENDC} {self.arch}
{Colors.BOLD}Hostname:{Colors.ENDC} {self.hostname}
{Colors.BOLD}User:{Colors.ENDC} {self.current_user} (UID {self.uid})
{Colors.BOLD}Uptime:{Colors.ENDC} {uptime//3600:.0f}h {uptime%3600//60:.0f}m
{Colors.BOLD}Filesystem Root:{Colors.ENDC} {self.fs_root}
{Colors.BOLD}Storage:{Colors.ENDC} {shutil.disk_usage(self.fs_root).free // (1024*1024)} MB free
""")
    
    def cmd_ssh_start(self, args):
        """启动SSH"""
        if self.ssh_server and self.ssh_server.is_alive():
            print("sshd: ssh service already running")
            return
        
        try:
            self.ssh_server = threading.Thread(target=self.run_ssh_server, daemon=True)
            self.ssh_server.start()
            print(f"Starting OpenSSH server: sshd [ OK ]")
            print(f"  Listening on 0.0.0.0:{self.ssh_port}")
        except Exception as e:
            print(f"Starting OpenSSH server: sshd [FAILED]")
            print(f"  Error: {e}")
    
    def cmd_ssh_stop(self, args):
        """停止SSH"""
        print("Stopping OpenSSH server: sshd [ OK ]")
        self.ssh_server = None
    
    def cmd_ssh(self, args):
        """SSH组件"""
        if not args:
            print("ssh: missing hostname")
            print("Usage: ssh [user@]hostname [command]")
            return
        
        target = args[0]
        remote_cmd = ' '.join(args[1:]) if len(args) > 1 else None
        
        username = self.current_user
        host = target
        
        if '@' in target:
            parts = target.split('@')
            if len(parts) == 2:
                username = parts[0] if parts[0] else self.current_user
                host = parts[1]
        
        if host in ['localhost', '127.0.0.1', self.hostname]:
            self._ssh_local(username, remote_cmd)
        else:
            self._ssh_remote(host, username, remote_cmd)
    
    def _ssh_local(self, username, command):
        """模 拟 本地SSH连接"""
        if username not in self.users:
            print(f"ssh: user {username} does not exist")
            return
        
        print(f"Connecting to {self.hostname} as {username}...")
        print(f"  OpenSSH_8.9p1, OpenSSL 3.0.2")
        print(f"  Authenticated to {self.hostname} ({username})")
        print("  Last login: " + datetime.now().strftime('%a %b %d %H:%M:%S'))
        
        if command:
            print(f"\n{Colors.BOLD}Remote command: {command}{Colors.ENDC}")
            parts = command.split()
            if parts and parts[0] in self.commands:
                old_user = self.current_user
                old_dir = self.current_dir
                old_uid = self.uid
                old_gid = self.gid
                
                self.current_user = username
                self.uid = self.users[username]["uid"]
                self.gid = self.users[username]["gid"]
                self.current_dir = self.users[username]["home"]
                
                self.commands[parts[0]](parts[1:])
                
                self.current_user = old_user
                self.uid = old_uid
                self.gid = old_gid
                self.current_dir = old_dir
            else:
                print(f"bash: {parts[0] if parts else ''}: command not found")
            return
        
        print(f"  Type 'exit' to disconnect\n")
        
        old_user = self.current_user
        old_dir = self.current_dir
        old_uid = self.uid
        old_gid = self.gid
        
        self.current_user = username
        self.uid = self.users[username]["uid"]
        self.gid = self.users[username]["gid"]
        self.current_dir = self.users[username]["home"]
        try:
            os.chdir(self._real_path(self.current_dir))
        except:
            pass
        
        try:
            while True:
                cmd_line = input(self.get_prompt()).strip()
                if cmd_line.lower() in ['exit', 'quit', 'logout']:
                    break
                elif cmd_line:
                    parts = cmd_line.split()
                    cmd = parts[0].lower()
                    args = parts[1:] if len(parts) > 1 else []
                    
                    if cmd in self.commands:
                        self.commands[cmd](args)
                    else:
                        print(f"bash: {cmd}: command not found")
        except KeyboardInterrupt:
            print("\nDisconnected")
        finally:
            self.current_user = old_user
            self.uid = old_uid
            self.gid = old_gid
            self.current_dir = old_dir
            try:
                os.chdir(self._real_path(self.current_dir))
            except:
                pass
        
        print("Connection to localhost closed.")
    
    def _ssh_remote(self, host, username, command):
        """模 拟 远程SSH"""
        print(f"Connecting to {host}...")
        print(f"  OpenSSH_8.9p1, OpenSSL 3.0.2")
        print(f"  Authenticated to {host}")
        print("  Last login: " + datetime.now().strftime('%a %b %d %H:%M:%S'))
        
        if command:
            print(f"\n{Colors.BOLD}Remote command: {command}{Colors.ENDC}")
            print(f"  [Executing on {host}]")
            print(f"  {Colors.DIM}-- Remote execution completed --{Colors.ENDC}")
            return
        
        print(f"  Type 'exit' to disconnect\n")
        
        while True:
            try:
                cmd = input(f"{Colors.GREEN}{username}@{host}{Colors.ENDC}$ ").strip()
                if cmd.lower() in ['exit', 'quit', 'logout']:
                    break
                elif cmd:
                    print(f"  {Colors.DIM}Remote command '{cmd}' executed on {host}{Colors.ENDC}")
            except KeyboardInterrupt:
                print("\nDisconnected")
                break
        
        print("Connection closed.")
    
    def cmd_ps(self, args):
        print(f"{Colors.BOLD}USER       PID  PPID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND{Colors.ENDC}")
        print(f"root         1     0   0.0  0.1   1234  5678 ?        Ss   Jan01   0:01 systemd")
        print(f"root         2     0   0.0  0.0      0     0 ?        S    Jan01   0:00 kthreadd")
        print(f"{self.current_user}{' ' * (8-len(self.current_user))}1000     1   0.1  0.5   2345  6789 pts/0    Ss   10:00   0:02 bash")
        print(f"{self.current_user}{' ' * (8-len(self.current_user))}1001  1000   0.5  1.2   3456  7890 pts/0    R+   10:01   0:01 python3 orisx.py")
    
    def cmd_kill(self, args):
        '''这个有用吗'''
        if not args:
            print("kill: usage: kill [-s sigspec | -n signum | -sigspec] pid | jobspec ...")
            return
        
        try:
            pid = int(args[0])
            print(f"Process {pid} terminated (signal 15)")
        except ValueError:
            print(f"kill: {args[0]}: invalid pid")
    
    def cmd_df(self, args):
        """磁盘使用情况"""
        total, used, free = shutil.disk_usage(self.fs_root)
        
        print(f"{Colors.BOLD}Filesystem     1K-blocks     Used Available Use% Mounted on{Colors.ENDC}")
        print(f"orisx_fs        {total//1024:10d} {used//1024:8d} {free//1024:9d} {used*100//total:3d}% /")
    
    def cmd_du(self, args):
        """目录大小"""
        path = args[0] if args else self.current_dir
        abs_path = self.resolve_path(path)
        real_path = self._real_path(abs_path)
        
        if not os.path.exists(real_path):
            print(f"du: cannot access '{path}': No such file or directory")
            return
        
        try:
            total_size = 0
            if os.path.isfile(real_path):
                total_size = os.path.getsize(real_path)
            else:
                for root, dirs, files in os.walk(real_path):
                    for f in files:
                        try:
                            total_size += os.path.getsize(os.path.join(root, f))
                        except:
                            pass
            
            print(f"{total_size//1024:8d} {path}")
        except Exception as e:
            print(f"du: {e}")
    
    def cmd_id(self, args):
        """用户ID"""
        print(f"uid={self.uid}({self.current_user}) gid={self.gid}({self.current_user})")
    
    def cmd_who(self, args):
        """显示登录用户"""
        print(f"{self.current_user}  tty1         {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    def cmd_uptime(self, args):
        """运行时间"""
        uptime = time.time() - self.boot_time
        days = uptime // 86400
        hours = (uptime % 86400) // 3600
        minutes = (uptime % 3600) // 60
        
        if days > 0:
            print(f" {uptime:.2f} up {days:.0f} day{'s' if days > 1 else ''}, {hours:.0f}:{minutes:02.0f},  1 user,  load average: 0.00, 0.01, 0.05")
        else:
            print(f" {uptime:.2f} up {hours:.0f}:{minutes:02.0f},  1 user,  load average: 0.00, 0.01, 0.05")
    
    def cmd_free(self, args):
        """内存使用"""
        print(f"{Colors.BOLD}              total        used        free      shared  buff/cache   available{Colors.ENDC}")
        print(f"Mem:         {1024:10d} {512:10d} {512:10d} {0:10d} {0:10d} {512:10d}")
        print(f"Swap:        {512:10d} {0:10d} {512:10d}")
    
    def cmd_env(self, args):
        """环境变量"""
        for key, value in sorted(self.env_vars.items()):
            print(f"{key}={value}")
    
    def cmd_export(self, args):
        """设置环境变量"""
        if not args:
            self.cmd_env([])
            return
        
        for arg in args:
            if '=' in arg:
                key, value = arg.split('=', 1)
                self.env_vars[key] = value
    
    def cmd_tree(self, args):
        path = args[0] if args else self.current_dir
        abs_path = self.resolve_path(path)
        real_path = self._real_path(abs_path)
        
        if not os.path.exists(real_path):
            print(f"tree: {path}: No such file or directory")
            return
        
        print(f"{abs_path}")
        self._print_tree(real_path, "")
    
    def _print_tree(self, path, prefix):
        """递归print"""
        try:
            items = sorted([item for item in os.listdir(path) if not item.startswith('.')])
            for i, item in enumerate(items):
                item_path = os.path.join(path, item)
                is_last = i == len(items) - 1
                
                if os.path.isdir(item_path):
                    print(f"{prefix}{'└── ' if is_last else '├── '}{Colors.BLUE}{item}/{Colors.ENDC}")
                    self._print_tree(item_path, prefix + ('    ' if is_last else '│   '))
                else:
                    print(f"{prefix}{'└── ' if is_last else '├── '}{item}")
        except PermissionError:
            print(f"{prefix}Permission denied")
    
    def cmd_find(self, args):
        """寻觅文件"""
        if not args:
            print("find: missing operand")
            return
        
        path = args[0]
        name = args[1] if len(args) > 1 else None
        abs_path = self.resolve_path(path)
        real_path = self._real_path(abs_path)
        
        if not os.path.exists(real_path):
            print(f"find: '{path}': No such file or directory")
            return
        
        self._find_files(real_path, name or "")
    
    def _find_files(self, path, name):
        """递归找"""
        try:
            if not name or name in os.path.basename(path):
                print(self._virtual_path(path))
            
            if os.path.isdir(path):
                for item in os.listdir(path):
                    self._find_files(os.path.join(path, item), name)
        except PermissionError:
            pass
    
    def cmd_grep(self, args):
        """搜索文本"""
        if len(args) < 2:
            print("grep: missing operand")
            return
        
        pattern = args[0]
        path = self.resolve_path(args[1])
        real_path = self._real_path(path)
        
        if not os.path.exists(real_path):
            print(f"grep: {args[1]}: No such file or directory")
            return
        
        if os.path.isdir(real_path):
            print(f"grep: {args[1]}: Is a directory")
            return
        
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    if pattern in line:
                        print(f"{i}: {line}", end='')
        except UnicodeDecodeError:
            try:
                with open(real_path, 'rb') as f:
                    content = f.read().decode('utf-8', errors='ignore')
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if pattern in line:
                            print(f"{i}: {line}")
            except Exception as e:
                print(f"grep: {e}")
        except Exception as e:
            print(f"grep: {e}")
    
    def cmd_head(self, args):
        """显示文件开头"""
        if not args:
            print("head: missing file operand")
            return
        
        n = 10
        path = args[0]
        if args[0].startswith('-'):
            n = int(args[0][1:])
            path = args[1] if len(args) > 1 else None
        
        if not path:
            print("head: missing file operand")
            return
        
        abs_path = self.resolve_path(path)
        real_path = self._real_path(abs_path)
        
        if not os.path.exists(real_path):
            print(f"head: cannot open '{path}' for reading: No such file or directory")
            return
        
        if os.path.isdir(real_path):
            print(f"head: {path}: Is a directory")
            return
        
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:n]
                print(''.join(lines), end='')
        except UnicodeDecodeError:
            try:
                with open(real_path, 'rb') as f:
                    content = f.read().decode('utf-8', errors='ignore')
                    lines = content.split('\n')[:n]
                    print('\n'.join(lines))
            except Exception as e:
                print(f"head: {e}")
        except Exception as e:
            print(f"head: {e}")
    
    def cmd_tail(self, args):
        """显示文件结尾"""
        if not args:
            print("tail: missing file operand")
            return
        
        n = 10
        path = args[0]
        if args[0].startswith('-'):
            n = int(args[0][1:])
            path = args[1] if len(args) > 1 else None
        
        if not path:
            print("tail: missing file operand")
            return
        
        abs_path = self.resolve_path(path)
        real_path = self._real_path(abs_path)
        
        if not os.path.exists(real_path):
            print(f"tail: cannot open '{path}' for reading: No such file or directory")
            return
        
        if os.path.isdir(real_path):
            print(f"tail: {path}: Is a directory")
            return
        
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(''.join(lines[-n:]), end='')
        except UnicodeDecodeError:
            try:
                with open(real_path, 'rb') as f:
                    content = f.read().decode('utf-8', errors='ignore')
                    lines = content.split('\n')
                    print('\n'.join(lines[-n:]))
            except Exception as e:
                print(f"tail: {e}")
        except Exception as e:
            print(f"tail: {e}")
    
    def cmd_wc(self, args):
        """统计行/词/字符数"""
        if not args:
            print("wc: missing file operand")
            return
        
        path = self.resolve_path(args[0])
        real_path = self._real_path(path)
        
        if not os.path.exists(real_path):
            print(f"wc: {args[0]}: No such file or directory")
            return
        
        if os.path.isdir(real_path):
            print(f"wc: {args[0]}: Is a directory")
            return
        
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = len(content.split('\n'))
                words = len(content.split())
                chars = len(content)
                print(f"{lines:8} {words:8} {chars:8} {args[0]}")
        except UnicodeDecodeError:
            try:
                with open(real_path, 'rb') as f:
                    content = f.read().decode('utf-8', errors='ignore')
                    lines = len(content.split('\n'))
                    words = len(content.split())
                    chars = len(content)
                    print(f"{lines:8} {words:8} {chars:8} {args[0]}")
            except Exception as e:
                print(f"wc: {e}")
        except Exception as e:
            print(f"wc: {e}")
    
    def cmd_sort(self, args):
        """排序"""
        if not args:
            print("sort: missing file operand")
            return
        
        path = self.resolve_path(args[0])
        real_path = self._real_path(path)
        
        if not os.path.exists(real_path):
            print(f"sort: {args[0]}: No such file or directory")
            return
        
        if os.path.isdir(real_path):
            print(f"sort: {args[0]}: Is a directory")
            return
        
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in sorted(lines):
                    if line.strip():
                        print(line, end='')
        except Exception as e:
            print(f"sort: {e}")
    
    def cmd_uniq(self, args):
        """去重"""
        if not args:
            print("uniq: missing file operand")
            return
        
        path = self.resolve_path(args[0])
        real_path = self._real_path(path)
        
        if not os.path.exists(real_path):
            print(f"uniq: {args[0]}: No such file or directory")
            return
        
        if os.path.isdir(real_path):
            print(f"uniq: {args[0]}: Is a directory")
            return
        
        try:
            with open(real_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                seen = set()
                for line in lines:
                    line = line.strip()
                    if line and line not in seen:
                        print(line)
                        seen.add(line)
        except Exception as e:
            print(f"uniq: {e}")
    
    def cmd_edit(self, args):
        """简单文本编辑（nano vim edit ）"""
        if not args:
            print("edit: missing file operand")
            print("Usage: edit [filename]")
            return
        
        filename = args[0]
        abs_path = self.resolve_path(filename)
        real_path = self._real_path(abs_path)
        
        if os.path.exists(real_path) and os.path.isdir(real_path):
            print(f"edit: {filename}: Is a directory")
            return
        
        content = ""
        if os.path.exists(real_path):
            try:
                with open(real_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(real_path, 'rb') as f:
                        content = f.read().decode('utf-8', errors='ignore')
                except:
                    pass
            except:
                pass
        
        print(f"\n{Colors.BOLD}Editing: {filename}{Colors.ENDC}")
        print(f"{Colors.DIM}Enter text. Type ':w' to save, ':q' to quit, ':wq' to save and quit{Colors.ENDC}")
        print(f"{Colors.DIM}Line numbers: Enter new line after current line{Colors.ENDC}\n")
        
        if content:
            print(f"{Colors.DIM}--- Current content ---{Colors.ENDC}")
            print(content.rstrip())
            print(f"{Colors.DIM}--- End of content ---{Colors.ENDC}\n")
        
        lines = content.split('\n') if content else ['']
        if lines and not lines[-1]:
            lines = lines[:-1]
        
        editing = True
        while editing:
            for i, line in enumerate(lines):
                line_num = f"{i+1:3d}"
                print(f"{Colors.DIM}{line_num}{Colors.ENDC} {line}")
            
            print(f"\n{Colors.DIM}--- Enter line (or command) ---{Colors.ENDC}")
            print(f"{Colors.BOLD}:{Colors.ENDC}line number to edit  {Colors.BOLD}:w{Colors.ENDC}save  {Colors.BOLD}:q{Colors.ENDC}quit  {Colors.BOLD}:wq{Colors.ENDC}save & quit  {Colors.BOLD}:d{Colors.ENDC}delete line")
            
            try:
                cmd = input(f"{Colors.GREEN}edit{Colors.ENDC}> ").strip()
                
                if not cmd:
                    new_line = input("> ").strip()
                    if new_line:
                        lines.append(new_line)
                    continue
                
                if cmd == ':w':
                    try:
                        os.makedirs(os.path.dirname(real_path), exist_ok=True)
                        with open(real_path, 'w', encoding='utf-8') as f:
                            f.write('\n'.join(lines))
                        print(f"{Colors.GREEN}File saved{Colors.ENDC}")
                    except Exception as e:
                        print(f"Error saving: {e}")
                    continue
                
                if cmd == ':q':
                    editing = False
                    print("Exiting editor")
                    continue
                
                if cmd == ':wq':
                    try:
                        os.makedirs(os.path.dirname(real_path), exist_ok=True)
                        with open(real_path, 'w', encoding='utf-8') as f:
                            f.write('\n'.join(lines))
                        print(f"{Colors.GREEN}File saved{Colors.ENDC}")
                    except Exception as e:
                        print(f"Error saving: {e}")
                    editing = False
                    print("Exiting editor")
                    continue
                
                if cmd.startswith(':d'):
                    try:
                        line_num = int(cmd.split()[1]) if len(cmd.split()) > 1 else None
                        if line_num and 1 <= line_num <= len(lines):
                            deleted = lines.pop(line_num - 1)
                            print(f"Deleted line {line_num}: {deleted}")
                        else:
                            print(f"Invalid line number. Lines: 1-{len(lines)}")
                    except (ValueError, IndexError):
                        print("Usage: :d <line_number>")
                    continue
                
                if cmd.startswith(':'):
                    try:
                        line_num = int(cmd[1:])
                        if 1 <= line_num <= len(lines):
                            print(f"{Colors.BOLD}Editing line {line_num}: {Colors.ENDC}{lines[line_num-1]}")
                            new_line = input("> ").strip()
                            if new_line:
                                lines[line_num-1] = new_line
                        else:
                            print(f"Invalid line number. Lines: 1-{len(lines)}")
                    except ValueError:
                        print(f"Unknown command: {cmd}")
                    continue
                
                lines.append(cmd)
                
            except KeyboardInterrupt:
                print("\nExiting editor (unsaved changes may be lost)")
                editing = False
        
        print()
    
    def cmd_reboot(self, args):
        print("Rebooting...")
        self.save_users()
        time.sleep(1)
        self.running = False
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    def cmd_shutdown(self, args):
        print("System is going down. Logging out...")
        self.save_users()
        time.sleep(1)
        self.running = False
    
    def run_ssh_server(self):
        """运行SSH？！"""
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('0.0.0.0', self.ssh_port))
            server.listen(5)
            
            while self.running:
                try:
                    client, addr = server.accept()
                    client.send(b"SSH-2.0-OpenSSH_8.9p1 OrisX\r\n")
                    data = client.recv(1024)
                    if data:
                        response = f"""
Welcome to OrisX!

This is a simulated SSH server.
To connect, use: ssh {self.current_user}@localhost -p {self.ssh_port}

Username: """
                        client.send(response.encode())
                        
                        try:
                            username = client.recv(1024).decode().strip()
                            if username in self.users:
                                client.send(b"Password: ")
                                password = client.recv(1024).decode().strip()
                                if password == self.users[username]["password"]:
                                    client.send(f"\nAuthenticated as {username}\n".encode())
                                    client.send(b"$ ")
                                else:
                                    client.send(b"\nAuthentication failed.\n")
                            else:
                                client.send(b"\nUser not found.\n")
                        except:
                            pass
                    
                    client.close()
                except:
                    pass
                time.sleep(0.1)
                
        except Exception as e:
            print(f"SSH server error: {e}")
    
    def run(self):
        """主循环在这里喵"""
        while self.running:
            try:
                if not self.logged_in:
                    time.sleep(0.1)
                    continue
                
                cmd_line = input(self.get_prompt()).strip()
                
                if not cmd_line:
                    continue
                
                self.history.append(cmd_line)
                
                parts = cmd_line.split()
                cmd = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                if '|' in cmd_line or '>' in cmd_line or '>>' in cmd_line:
                    try:
                        cwd = self._real_path(self.current_dir)
                        result = subprocess.run(cmd_line, shell=True, 
                                              capture_output=True, text=True,
                                              cwd=cwd)
                        if result.stdout:
                            print(result.stdout, end='')
                        if result.stderr:
                            print(result.stderr, end='')
                    except Exception as e:
                        print(f"Error: {e}")
                elif cmd in self.commands:
                    self.commands[cmd](args)
                else:
                    print(f"bash: {cmd}: command not found")
                
            except KeyboardInterrupt:
                print(f"\n^C")
            except EOFError:
                print()
                break
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    try:
        if os.name == 'nt':
            os.system('')
        
        system = OrisXSystem()
        system.run()
        
    except KeyboardInterrupt:
        print("\nSystem interrupted")
    except Exception as e:
        print(f"System error: {e}")
        import traceback
        traceback.print_exc()



"""
终于写完了awa
我凑个行数()
"""