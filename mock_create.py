import pandas as pd

# Load the original dataset
file_path = 'history.csv'
df = pd.read_csv(file_path)

# Decide on the number of rows for the subset
num_rows = 100  # For example, take the first 100 rows

# Create the subset
subset_df = df.iloc[:num_rows]

# Save the subset to a new file
mock_file_path = './tests/mock_history.csv'
subset_df.to_csv(mock_file_path, index=False)

print(f"A subset of {num_rows} rows has been saved to '{mock_file_path}'.")
