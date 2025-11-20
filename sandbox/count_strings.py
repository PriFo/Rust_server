import os
import asyncio
import aiofiles


notebook_path = 'C:\\Users\\screb\\Desktop\\Dev\\rust_server\\Rust_server'
pc_path = 'C:\\Users\\screb\\Desktop\\Dev\\Rust_server'
c_path = 'C:\\'
inclusive_dirs: list = ['.git', '__pycache__', 'jsons', 'txts', 'user_help_photos']
inclusive_files: list = ['.env', '.gitignore']


async def sum_counts(counts: list) -> int:
    result = 0
    for count in counts:
        result += count
    return result


async def create_tasks_files(dir_list: list, dir_path: str) -> list:
    path_list: list = dir_path.split(sep='\\')
    if path_list[len(path_list) - 1] not in inclusive_dirs:
        tasks = []
        for file in dir_list:
            if file not in inclusive_files:
                tasks.append(
                    asyncio.create_task(
                        count_strings_in_file(dir_path + '\\' + file)
                    )
                )
        return tasks


async def count_strings_in_file(file_path: str) -> int:
    count = 0
    try:
        async with aiofiles.open(file_path, mode='r', encoding='utf-8') as file:
            while await file.readline() != '':
                count += 1
        # print(f'{file_path=}: {count=}')
        return count
    except PermissionError:
        try:
            dir_list = os.listdir(file_path)
            tasks = await create_tasks_files(dir_list, file_path)
            counts = await asyncio.gather(*tasks)
            return await sum_counts(counts)
        except:
            print(f'{file_path} is skipped')
            return 0
    except UnicodeDecodeError:
        print(f'{file_path} is skipped')
        return 0


async def try_to_check_all_files_on_pc():
    dir_list = os.listdir(c_path)
    print('\033[33m')
    tasks = []
    tasks = await create_tasks_files(dir_list, c_path)
    counts = await asyncio.gather(*tasks)
    result = await sum_counts(counts)
    print('\033[37m')
    print(f'Strings in project: {result}')


async def main():
    is_pc = False
    try:
        dir_list = os.listdir(notebook_path)
    except:
        is_pc = True
        dir_list = os.listdir(pc_path)
    finally:
        print('\033[33m')
        tasks = []
        if is_pc:
            tasks = await create_tasks_files(dir_list, pc_path)
        else:
            tasks = await create_tasks_files(dir_list, notebook_path)
        counts = await asyncio.gather(*tasks)
        result = await sum_counts(counts)
        print('\033[37m')
        print(f'Strings in project: {result}')


if __name__ == '__main__':
    asyncio.run(main())
    # asyncio.run(try_to_check_all_files_on_pc())
