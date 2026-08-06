import csv

import numpy as np


def calculate_average(filename, column_index):
    """
    Calculate the average of a specified column in a CSV file.

    Args:
        filename (str): The name of the CSV file.
        column_index (int): The index of the column to calculate the average for.

    Returns:
        float: The average of the specified column.
    """
    try:
        with open(filename, 'r') as file:
            reader = csv.reader(file)
            data = [row[column_index] for row in list(reader)[1:]]  # Skip header row
            data = [float(value) for value in data]
            average = np.mean(data)
            return average
    except FileNotFoundError:
        print(f"File {filename} not found.")
        return None
    except IndexError:
        print(f"Column index {column_index} out of range.")
        return None
    except ValueError:
        print("Invalid data in the column.")
        return None

def main():
    filename = 'data.csv'
    column_index = 1  # Second column (0-indexed)
    average = calculate_average(filename, column_index)
    if average is not None:
        print(f"The average of the second column is: {average}")

if __name__ == "__main__":
    main()