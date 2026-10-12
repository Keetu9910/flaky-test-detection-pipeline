import pandas as pd
import os

def main():
    # 1. Load the original IDoFT dataset (downloaded during the GitHub Action)
    idoft_path = 'pr-data.csv'
    if not os.path.exists(idoft_path):
        print(f"Error: {idoft_path} not found. Ensure it was downloaded successfully.")
        return

    try:
        idoft_df = pd.read_csv(idoft_path)
    except Exception as e:
        print(f"Error reading IDoFT dataset: {e}")
        return

    # IDoFT uses a very specific column name for the test
    idoft_test_col = 'Fully-Qualified Test Name (packageName.ClassName.methodName)'
    
    # Verify the expected columns exist in the downloaded IDoFT CSV
    required_idoft_cols = ['Project URL', 'SHA', idoft_test_col]
    for col in required_idoft_cols:
        if col not in idoft_df.columns:
            print(f"Error: Column '{col}' not found in {idoft_path}. Available columns: {list(idoft_df.columns)}")
            return

    # Create a unified unique key for known flaky tests
    # Format: ProjectURL_SHA_TestName
    idoft_df['unique_key'] = idoft_df['Project URL'].astype(str) + "_" + \
                             idoft_df['SHA'].astype(str) + "_" + \
                             idoft_df[idoft_test_col].astype(str)
                             
    known_flaky_tests = set(idoft_df['unique_key'].dropna().str.strip())

    # 2. Load the newly generated aggregated results from your tools
    new_results_files = ['nondex_summary.csv', 'idflakies_summary.csv', 'flakesync_td_tests.csv']
    all_detected = []
    
    for file in new_results_files:
        if os.path.exists(file):
            try:
                df = pd.read_csv(file)
                
                # Check if file has data and contains the expected output columns from your aggregator
                if not df.empty and 'Project URL' in df.columns and 'SHA' in df.columns and 'Test Name' in df.columns:
                    # Create the same unified key format to match against IDoFT
                    df['unique_key'] = df['Project URL'].astype(str) + "_" + \
                                       df['SHA'].astype(str) + "_" + \
                                       df['Test Name'].astype(str)
                    
                    df['Source Tool'] = file.split('_')[0] # Tags whether it came from nondex, idflakies, etc.
                    all_detected.append(df)
                elif not df.empty:
                    print(f"Warning: {file} is missing required columns ('Project URL', 'SHA', 'Test Name').")
            except Exception as e:
                print(f"Error reading {file}: {e}")

    if not all_detected:
        print("No summary CSVs found from the tools to compare.")
        return

    combined_detected_df = pd.concat(all_detected, ignore_index=True)

    # 3. Filter for unique tests (tests that exist in our tools' runs but NOT in IDoFT)
    unique_tests_df = combined_detected_df[~combined_detected_df['unique_key'].isin(known_flaky_tests)]

    # Clean up the helper key column before saving
    unique_tests_df = unique_tests_df.drop(columns=['unique_key'])

    # 4. Save to a new CSV
    output_filename = 'unique_flaky_tests.csv'
    unique_tests_df.to_csv(output_filename, index=False)
    
    print(f"Comparison complete. Found {len(unique_tests_df)} unique flaky test entries across all tools.")
    print(f"Saved unique discoveries to {output_filename}")

if __name__ == "__main__":
    main()
