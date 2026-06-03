from db.repository import (
    rebuild_recipe_daily_reaction,
    count_recipe_daily_reaction,
)


def main():
    rebuild_recipe_daily_reaction()

    row_count = count_recipe_daily_reaction()

    print(f"done. recipe_daily_reaction row_count={row_count}")


if __name__ == "__main__":
    main()