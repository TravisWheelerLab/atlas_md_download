import os, glob, shutil, sys, argparse
import requests, gc, random, time
import pandas as pd
from zipfile import ZipFile
from datetime import date
from toml import loads, dumps

def check_directories(pdb):
    """
    Mostly in the case the script is restarted to skip over already downloaded data
    """
    data_dir = os.path.join(os.getcwd(), 'data')
    subdirectories = [
        os.path.join(data_dir, pdb),
        os.path.join(data_dir, f"{pdb}_prod_R1"),
        os.path.join(data_dir, f"{pdb}_prod_R2"),
        os.path.join(data_dir, f"{pdb}_prod_R3")
    ]
    
    # Check if any required subdirectory is missing
    for subdir in subdirectories:
        if not os.path.exists(subdir):
            return True  # Return True if any directory is missing
    
    return False  # Return False if all directories exist

def download_and_extract(url, output_dir):
    # Make GET request to the URL
    response = requests.get(url)
    
    # Ensure request was successful
    if response.status_code == 200:
        # Create subdirectory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Define the path for the downloaded file
        zip_path = os.path.join(output_dir, 'ATLAS_parsable_latest.zip')
        
        # Save the response content to a file
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        # Extract the contents of the ZIP file
        with ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        
        print("Download and extraction completed successfully.")
    else:
        print(f"Failed to download file. Status code: {response.status_code}")

def read_and_filter_tsv(output_dir, pdb_value=None):
    # Find the TSV file ending with "_ATLAS_info.tsv" in the output directory
    tsv_files = [file for file in os.listdir(output_dir) if file.endswith('_ATLAS_info.tsv')]
    
    if len(tsv_files) == 0:
        print("No TSV files found in the output directory.")
        return None
    
    # Read the first matching TSV file into a DataFrame
    tsv_file_path = os.path.join(output_dir, tsv_files[0])
    df = pd.read_csv(tsv_file_path, sep='\t')
    
    # Filter columns
    columns_to_keep = ['PDB', 'UniProt', 'organism', 'protein_name']
    df_filtered = df[columns_to_keep]

    if pdb_value is not None:
        # Find the index of the row with the specified PDB value
        start_index = df_filtered[df_filtered['PDB'] == pdb_value].index.tolist()
        if len(start_index) > 0:
            start_index = start_index[0]
            df_filtered = df_filtered.iloc[start_index:]
        else:
            print(f"No rows found with PDB value '{pdb_value}'.")
    
    return df_filtered

def load_template():
    # Load the template TOML file
    template_file = "template.toml"
    with open(template_file, "r") as f:
        template_content = f.read()
    return template_content

def replace_placeholders(template, row, prod_id, orcid):
    # Determine the production identifier suffix
    if prod_id == 1:
        prod_suffix = "_prod_R1"
    elif prod_id == 2:
        prod_suffix = "_prod_R2"
    elif prod_id == 3:
        prod_suffix = "_prod_R3"
    else:
        raise ValueError("Invalid production identifier. Use values 1, 2, or 3.")

    # Replace placeholders in the template with values from the row
    replaced_template = template.replace("<<df_organism>>", row["organism"])
    replaced_template = replaced_template.replace("<<df_protein_name>>", row["protein_name"])
    replaced_template = replaced_template.replace("<<df_UniProt>>", row["UniProt"])
    replaced_template = replaced_template.replace("<<df_PDB>>", row["PDB"])
    replaced_template = replaced_template.replace("<<df_PDB_prod>>", row["PDB"] + prod_suffix)
    replaced_template = replaced_template.replace("<<today>>", str(date.today()))
    replaced_template = replaced_template.replace("<<df_orcid>>", str(orcid)) 

    save_toml(row["PDB"], replaced_template, os.getcwd(), prod_suffix)

def save_toml(pdb, content, output_dir, prod_suffix):
    # Create a subdirectory in "data" with the PDB name
    pdb_dir = os.path.join(output_dir, "data", pdb)
    os.makedirs(pdb_dir, exist_ok=True)
    
    # Save the TOML content in a file named after the PDB
    toml_file = os.path.join(pdb_dir, f"{pdb}{prod_suffix}.toml")
    with open(toml_file, "w") as f:
        f.write(content)

def download_data_file(pdb, output_dir):
    # Download the associated data file
    data_url = f'https://www.dsimb.inserm.fr/ATLAS/api/ATLAS/total/{pdb}'
    pdb_dir = os.path.join(output_dir, "data", pdb)
    data_file = os.path.join(pdb_dir, f"{pdb}_total.zip")
    
    # Create necessary directories
    os.makedirs(pdb_dir, exist_ok=True)
    os.makedirs(os.path.join(pdb_dir, f"{pdb}_prod_R1"), exist_ok=True)
    os.makedirs(os.path.join(pdb_dir, f"{pdb}_prod_R2"), exist_ok=True)
    os.makedirs(os.path.join(pdb_dir, f"{pdb}_prod_R3"), exist_ok=True)
    
    max_attempts = 3
    attempt = 0
    success = False

    while attempt < max_attempts and not success:
        attempt += 1
        try:
            response = requests.get(data_url, stream=True)
            if response.status_code == 200:
                with open(data_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024): 
                        if chunk:  
                            f.write(chunk)
                            f.flush() 
                print(f"Downloaded data file for {pdb}.")
                
                # Extract the contents of the ZIP file
                with ZipFile(data_file, 'r') as zip_ref:
                    zip_ref.extractall(pdb_dir)
            
                # Move files to respective directories
                extracted_files = glob.glob(os.path.join(pdb_dir, '*'))
                for item in extracted_files:
                        if os.path.isfile(item):  # Check if the item is a file
                            file_name_with_ext = os.path.basename(item)  # Get file name with extension
                            file_name, file_ext = os.path.splitext(file_name_with_ext)  # Separate file name and extension
                            
                            if '_prod_R1' in file_name:
                                target_dir = os.path.join(pdb_dir, f"{pdb}_prod_R1")
                            elif '_prod_R2' in file_name:
                                target_dir = os.path.join(pdb_dir, f"{pdb}_prod_R2")
                            elif '_prod_R3' in file_name:
                                target_dir = os.path.join(pdb_dir, f"{pdb}_prod_R3")
                            else:
                                if file_ext == '.top' or file_ext == '.txt' or '_start.gro' in file_name_with_ext:
                                    target_dir_r1 = os.path.join(pdb_dir, f"{pdb}_prod_R1")
                                    target_dir_r2 = os.path.join(pdb_dir, f"{pdb}_prod_R2")
                                    target_dir_r3 = os.path.join(pdb_dir, f"{pdb}_prod_R3")
                                    
                                    # Copy file to all three respective directories
                                    shutil.copy(item, os.path.join(target_dir_r1, file_name_with_ext))
                                    shutil.copy(item, os.path.join(target_dir_r2, file_name_with_ext))
                                    shutil.copy(item, os.path.join(target_dir_r3, file_name_with_ext))

                                    # Remove original file after copying to all directories
                                    os.unlink(item)
                                continue
                            
                            # Move file to the respective directory
                            shutil.move(item, os.path.join(target_dir, file_name_with_ext))
                
                # Delete the ZIP file after extraction
                os.unlink(data_file)

                # Define the target directory where you want to move the directories
                target_dir = os.path.join(output_dir, "data")

                # Move directories to the target directory (keeping them under 'data')
                shutil.move(os.path.join(pdb_dir, f"{pdb}_prod_R1"), target_dir)
                shutil.move(os.path.join(pdb_dir, f"{pdb}_prod_R2"), target_dir)
                shutil.move(os.path.join(pdb_dir, f"{pdb}_prod_R3"), target_dir)
                
                # Delete pdb_dir after moving prod directories
                shutil.rmtree(pdb_dir)           
                gc.collect()                  
            else:
                print(f"Failed to download data file for {pdb}.")
                time.sleep(random.uniform(1, 5))  # Random pause between attempts
        except Exception as e:
            print(f"Error occurred during download attempt {attempt}: {e}")
            time.sleep(random.uniform(1, 5))  # Random pause between attempts
    if not success:
        print(f"Failed to download data file for {pdb} after {max_attempts} attempts.")


def main():
    parser = argparse.ArgumentParser(description='Filter TSV file based on PDB value.')
    parser.add_argument('pdb', type=str, help='Specify a PDB value to filter rows starting with this PDB')

    args = parser.parse_args()
    pdb_value = args.pdb

    # Check for ORC ID
    if len(sys.argv) > 1:
        orcid = sys.argv[1] 
    else:
        print("ORCID not provided. Please provide an ORCID as a command-line argument.")
        sys.exit(1)
    
    # URL to download the file from
    url = 'https://www.dsimb.inserm.fr/ATLAS/api/parsable'
    
    # Subdirectory to save the file and extract its contents
    output_dir = os.path.join(os.getcwd(), 'output')
    
    # Download and extract the file
    download_and_extract(url, output_dir)
    
    # Read and filter the TSV file
    df = read_and_filter_tsv(output_dir, pdb_value=pdb_value)
    if df is not None:
        # Load the template TOML content
        template_content = load_template()
        
        # Create a subdirectory "data" if it doesn't exist
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Process each row in the DataFrame
        for _, row in df.iterrows():
            # Replace placeholders in the template with values from the row
            for prod_id in [1, 2, 3]:
                replace_placeholders(template_content, row, prod_id, orcid)
            
            # Save the modified TOML content in a subdirectory named after the PDB
            #save_toml(row["PDB"], replaced_template, os.getcwd())
            
            # Download the associated data file
            if check_directories(row["PDB"]):
                download_data_file(row["PDB"], os.getcwd())

    print("TOML files and data files created successfully.")

if __name__ == "__main__":
    main()
