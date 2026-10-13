import pandas as pd
import os

def load_data(filepath):
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    return pd.DataFrame()

# Load IDoFT dataset
idoft_df = load_data('pr-data.csv')
idoft_tests = set()
if not idoft_df.empty:
    # Assuming standard IDoFT columns for test names
    if 'Fully-Qualified Test Name (packageName.ClassName.methodName)' in idoft_df.columns:
        idoft_tests = set(idoft_df['Fully-Qualified Test Name (packageName.ClassName.methodName)'].dropna())

# Load detected data from the newly organized folders
idflakies_df = load_data('idflakies_summary.csv')
nondex_df = load_data('nondex_summary.csv')
flakesync_df = load_data('flakesync_td_tests.csv')

# Calculate total detected
idflakies_total = len(idflakies_df) if not idflakies_df.empty else 0
nondex_total = len(nondex_df) if not nondex_df.empty else 0
flakesync_total = len(flakesync_df) if not flakesync_df.empty else 0

# Function to find unique tests
def get_unique(df):
    unique_list = []
    if not df.empty and 'Test Name' in df.columns:
        for _, row in df.iterrows():
            if row['Test Name'] not in idoft_tests:
                proj = row.get('Project Name', 'Unknown')
                sha = row.get('SHA', 'Unknown')
                test = row['Test Name']
                unique_list.append(f"- {proj}, {sha}, {test}")
    return unique_list

idflakies_unique = get_unique(idflakies_df)
nondex_unique = get_unique(nondex_df)
flakesync_unique = get_unique(flakesync_df)

# Write formatted output
with open('unique_tests.txt', 'w') as f:
    f.write("Flakies:\n")
    f.write(f"iDFlakies: {idflakies_total}\n")
    f.write(f"nondex: {nondex_total}\n")
    f.write(f"flakesync: {flakesync_total}\n\n")
    
    f.write("unique flakies:\n")
    f.write(f"iDflakies: {len(idflakies_unique)}\n")
    for item in idflakies_unique:
        f.write(f"{item}\n")
        
    f.write(f"Nondex: {len(nondex_unique)}\n")
    for item in nondex_unique:
        f.write(f"{item}\n")
        
    f.write(f"flakesync: {len(flakesync_unique)}\n")
    for item in flakesync_unique:
        f.write(f"{item}\n")

print("Generated unique_tests.txt successfully.")
