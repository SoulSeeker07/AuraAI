# Import the necessary library for reading CSV files
import csv


def calculate_average(filename, column_index):
    """
    Calculate the average of a specified column in a CSV file.

    Args:
        filename (str): The name of the CSV file.
        column_index (int): The index of the column for which to calculate the average.

    Returns:
        float: The average of the specified column.
    """
    try:
        # Initialize sum and count variables
        total = 0
        count = 0

        # Open the CSV file
        with open(filename, 'r') as file:
            # Create a CSV reader
            reader = csv.reader(file)

            # Skip the header row
            next(reader)

            # Iterate over each row in the CSV file
            for row in reader:
                # Check if the row has enough columns
                if len(row) > column_index:
                    # Try to convert the column value to a float
                    try:
                        value = float(row[column_index])
                        # Add the value to the total and increment the count
                        total += value
                        count += 1
                    except ValueError:
                        # Handle non-numeric values
                        print(f"Skipping non-numeric value '{row[column_index]}' in row {count + 1}")

        # Check if any values were found
        if count == 0:
            print("No numeric values found in the specified column.")
            return None
        else:
            # Calculate and return the average
            return total / count

    except FileNotFoundError:
        # Handle the case where the file does not exist
        print(f"File '{filename}' not found.")
        return None

def main():
    # Specify the filename and column index
    filename = 'data.csv'
    column_index = 1  # Second column (0-indexed)

    # Calculate and print the average
    average = calculate_average(filename, column_index)
    if average is not None:
        print(f"The average of the second column is: {average}")

if __name__ == "__main__":
    main()