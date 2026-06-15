import subprocess
import psutil

def kill_process_by_script(script_name):
    """Kill Python processes running specific scripts"""
    killed = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and script_name in ' '.join(cmdline):
                print(f"Killing {script_name} (PID: {proc.info['pid']})")
                subprocess.run(['taskkill', '/PID', str(proc.info['pid']), '/F'])
                killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):  
            pass
    
    if not killed:
        print(f"No running process found for {script_name}")

kill_process_by_script("grading,serial,time(A).py")
kill_process_by_script("grading,serial,time(B).py")
kill_process_by_script("grading,serial,time(C).py")
kill_process_by_script("grading,serial,time(D).py")
kill_process_by_script("grading,color,serial,timing(A).py")
kill_process_by_script("grading,color,serial,timing(B).py")
kill_process_by_script("grading,color,serial,timing(C).py")
kill_process_by_script("grading,color,serial,timing(D).py")
kill_process_by_script("textured(A).py")
kill_process_by_script("textured(B).py")
kill_process_by_script("textured(C).py")
kill_process_by_script("textured(D).py")