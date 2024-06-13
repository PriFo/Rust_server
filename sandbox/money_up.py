import datetime as dt


def get_rate_deposit(year_percent: float, leap_year: bool = False) -> float:
    return (year_percent / 366) if leap_year else (year_percent / 365)


def is_leap_year() -> bool:
    year = dt.datetime.now().year
    return True if year // 4 == 0 else False


def count_days(this_date: dt.date, last_date: dt.date):
    return last_date - this_date


def days_in_month(month: int) -> int:
    if month in (4, 6, 9, 11):
        return 30
    elif month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    elif is_leap_year():
        return 29
    else:
        return 28


def main():
    year_percent: int = int(input('Введите годовую ставку: '))
    leap_year: bool = is_leap_year()
    rate_deposit: float = get_rate_deposit(year_percent / 100, leap_year)
    money: float = float(input('Введите нынешний остаток по вкладу: '))
    new_percents: float = 0.0
    percents: float = 0.0
    new_money: float = money
    this_date: dt.date = dt.date.today()
    last_date: str = input('Введите последнюю дату, когда вы хотите закрыть вклад (YYYY-MM-DD): ')
    last_date: dt.date = dt.date.fromisoformat(last_date)
    date_of_up: str = input('Введите дату поступления процентов на вклад (YYYY-MM-DD): ')
    date_of_up: dt.date = dt.date.fromisoformat(date_of_up)
    for day in range(1, count_days(this_date, last_date).days, 1):
        if count_days(this_date, date_of_up).days == 0:
            percents += new_percents
            new_money += new_percents
            new_percents = 0
            date_of_up += dt.timedelta(days=days_in_month(date_of_up.month))
        new_percents += new_money * rate_deposit
        this_date += dt.timedelta(days=1)
    print(f'Ваши средства на начало периода: {money} \
          \nВаши средства на конец периода: {new_money} \
          \nПроценты по вкладу за данный период: {percents}\
          \nНеначисленные проценты: {new_percents}')


if __name__ == '__main__':
    main()