import os
import asyncio
import aiofiles


async def count_strings(file_path: str):
    count = 0
    try:
        async with aiofiles.open(file_path, mode='r', encoding='utf-8') as file:
            while await file.readline() != '':
                count += 1
        return count
    except PermissionError as e:
        print(f'{file_path} is skipped')
        return 0


async def main():
    path = 'C:\\Users\\screb\\Desktop\\Rust_server'
    dir_list = os.listdir(path)
    print('\033[33m')
    print(*dir_list, sep='\n')
    print('\033[37m')
    tasks = []
    for file in dir_list:
        tasks.append(
            asyncio.create_task(
                count_strings(path + '\\' + file)
            )
        )
    counts = await asyncio.gather(*tasks)
    result = 0
    for count in counts:
        result += count
    print(f'Strings in project: {result}')


if __name__ == '__main__':
    asyncio.run(main())