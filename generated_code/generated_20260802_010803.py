import csv


def calculate_average(filename, column_index):
    """
    Calculate the average of a specified column in a CSV file.

    Args:
        filename (str): The name of the CSV file.
        column_index (int): The index of the column to calculate the average for (0-indexed).

    Returns:
        float: The average of the specified column.
    """
    total = 0
    count = 0
    with open(filename, 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row
        for row in reader:
            try:
                total += float(row[column_index])
                count += 1
            except (IndexError, ValueError):
                # Skip rows with missing or non-numeric values in the specified column
                pass
    if count == 0:
        raise ZeroDivisionError("Cannot calculate average of empty or non-numeric column")
    return total / count

def main():
    filename = 'data.csv'
    column_index = 1  # 0-indexed, so 1 refers to the second column
    average = calculate_average(filename, column_index)
    print(f"The average of the second column is: {average}")

if __name__ == "__main__":
    main()