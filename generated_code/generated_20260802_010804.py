import csv


def calculate_average(filename):
    """
    Calculate the average of the second column in a CSV file.

    Args:
        filename (str): The name of the CSV file.

    Returns:
        float: The average of the second column.
    """
    total = 0
    count = 0
    with open(filename, 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header row
        for row in reader:
            if len(row) > 1:
                try:
                    total += float(row[1])
                    count += 1
                except ValueError:
                    # Handle non-numeric values in the second column
                    pass
    if count == 0:
        raise ZeroDivisionError("Cannot calculate average of zero values")
    return total / count

def main():
    filename = 'data.csv'
    try:
        average = calculate_average(filename)
        print(f"The average of the second column is: {average}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()