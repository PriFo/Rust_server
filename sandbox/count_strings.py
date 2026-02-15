"""
Кроссплатформенный скрипт для подсчета строк в файлах проекта
Поддерживает Windows, Linux и macOS
"""
import os
import asyncio
import aiofiles
from pathlib import Path
from typing import List


# Кроссплатформенные пути - используем pathlib.Path
# Определяем текущую директорию проекта автоматически
_project_root = Path(__file__).parent.parent
_project_root_alt = Path.cwd()

# Если скрипт запущен из sandbox, берем parent, иначе используем cwd
if Path(__file__).parent.name == 'sandbox':
    project_path = _project_root
else:
    project_path = _project_root_alt

# Для корня диска - кроссплатформенное определение
if os.name == 'nt':  # Windows
    root_path = Path('C:/')
else:  # Linux/macOS
    root_path = Path('/')

inclusive_dirs: List[str] = ['.git', '__pycache__', 'jsons', 'txts', 'user_help_photos', '.venv']
inclusive_files: List[str] = ['.env', '.gitignore']


async def sum_counts(counts: List[int]) -> int:
    """Суммирует количество строк из списка"""
    result = 0
    for count in counts:
        result += count
    return result


async def create_tasks_files(dir_list: List[str], dir_path: Path) -> List[asyncio.Task]:
    """Создает задачи для подсчета строк в файлах директории"""
    # Проверяем, не в исключенной ли директории мы находимся
    if dir_path.name not in inclusive_dirs:
        tasks = []
        for file in dir_list:
            if file not in inclusive_files:
                file_path = dir_path / file
                tasks.append(
                    asyncio.create_task(
                        count_strings_in_file(file_path)
                    )
                )
        return tasks
    return []


async def count_strings_in_file(file_path: Path) -> int:
    """Подсчитывает количество строк в файле"""
    count = 0
    try:
        async with aiofiles.open(file_path, mode='r', encoding='utf-8') as file:
            while await file.readline() != '':
                count += 1
        return count
    except PermissionError:
        # Если это директория, обрабатываем рекурсивно
        try:
            dir_list = os.listdir(file_path)
            tasks = await create_tasks_files(dir_list, file_path)
            counts = await asyncio.gather(*tasks)
            return await sum_counts(counts)
        except Exception:
            print(f'{file_path} is skipped (PermissionError)')
            return 0
    except UnicodeDecodeError:
        print(f'{file_path} is skipped (UnicodeDecodeError)')
        return 0
    except Exception as e:
        print(f'{file_path} is skipped ({type(e).__name__}: {e})')
        return 0


async def try_to_check_all_files_on_root():
    """Пытается проверить все файлы на корневом диске (ОСТОРОЖНО: может быть медленно)"""
    try:
        dir_list = os.listdir(root_path)
        print('\033[33m')
        tasks = await create_tasks_files(dir_list, root_path)
        counts = await asyncio.gather(*tasks)
        result = await sum_counts(counts)
        print('\033[37m')
        print(f'Strings in root: {result}')
    except PermissionError:
        print(f'\033[31mPermission denied: cannot access {root_path}\033[37m')


async def main():
    """Основная функция - подсчитывает строки в проекте"""
    print(f'Analyzing project at: {project_path}')
    
    try:
        dir_list = os.listdir(project_path)
    except Exception as e:
        print(f'Error accessing project path: {e}')
        return
    
    print('\033[33m')  # Желтый цвет
    tasks = await create_tasks_files(dir_list, project_path)
    
    if not tasks:
        print('No files to analyze')
        return
    
    counts = await asyncio.gather(*tasks)
    result = await sum_counts(counts)
    print('\033[37m')  # Сброс цвета
    print(f'Strings in project: {result}')


if __name__ == '__main__':
    asyncio.run(main())
    # asyncio.run(try_to_check_all_files_on_pc())
