import csv

def calculate_average(filename):
    """
    Calculate the average of the second column in a CSV file.

    Args:
        filename (str): The name of the CSV file.

    Returns:
        float: The average of the second column.
    """
    # Initialize sum and count variables
    total = 0
    count = 0

    # Open the CSV file
    with open(filename, 'r') as file:
        # Create a CSV reader
        reader = csv.reader(file)

        # Iterate over each row in the CSV file
        for row in reader:
            # Check if the row has at least two columns
            if len(row) >= 2:
                try:
                    # Attempt to convert the second column to a float
                    value = float(row[1])
                    # Add the value to the total and increment the count
                    total += value
                    count += 1
                except ValueError:
                    # If the conversion fails, skip this row
                    pass

    # Check if any values were found
    if count == 0:
        raise ValueError("No numeric values found in the second column")

    # Calculate and return the average
    return total / count

def main():
    filename = 'data.csv'
    average = calculate_average(filename)
    print(f"The average of the second column is: {average}")

if __name__ == "__main__":
    main()