import subprocess

# Список путей к скриптам, которые нужно запустить
script_paths = [
    'main.py',
    'Site.py'
]

# Список для хранения процессов
processes = []

# Запускаем каждый скрипт в отдельном процессе
for script_path in script_paths:
    process = subprocess.Popen(['python3', script_path])
    processes.append(process)

# Дожидаемся завершения всех процессов
for process in processes: 
    process.wait()