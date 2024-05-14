import os, glob, shutil, sys
import requests, gc, random, time
import pandas as pd
from zipfile import ZipFile
from datetime import date
from toml import loads, dumps

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
        
        print("ATLAS metadata download and extraction completed successfully.")
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
    else:
        # Start from the beginning if pdb_value is None
        start_index = 0
        df_filtered = df_filtered.iloc[start_index:]
    
    return df_filtered

def load_template():
    # Load the template TOML file
    template_file = "template.toml"
    with open(template_file, "r") as f:
        template_content = f.read()
    return template_content

def replace_placeholders(template, row, prod_id, orcid, data_dir):
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

    save_toml(row["PDB"], replaced_template, data_dir, prod_suffix)

def save_toml(pdb, content, output_dir, prod_suffix):
    pdb_dir = os.path.join(output_dir, pdb + prod_suffix)
    
    if not os.path.exists(pdb_dir):
        return
    
    # Save the TOML content in a mdrepo-metadata.toml
    toml_file = os.path.join(pdb_dir, f"mdrepo-metadata.toml")
    with open(toml_file, "w") as f:
        f.write(content)

def main():
    base_dir = os.getcwd()

    # Check for ORC ID
    if len(sys.argv) > 1:
        orcid = sys.argv[1] 
    else:
        print("ORCID not provided. Please provide an ORCID as a command-line argument.")
        sys.exit(1)

    pdb_value = None

    if len(sys.argv) > 2:
        data_dir = os.path.join(base_dir, sys.argv[2])
    else:
        data_dir = os.path.join(base_dir, "data")
    
    # URL to download the file from
    url = 'https://www.dsimb.inserm.fr/ATLAS/api/parsable'
    
    # Subdirectory to save the file and extract its contents
    output_dir = os.path.join(base_dir, 'output')
    
    # Download and extract the file
    download_and_extract(url, output_dir)
    
    # Read and filter the TSV file
    df = read_and_filter_tsv(output_dir, pdb_value=pdb_value)
    if df is not None:
        # Load the template TOML content
        template_content = load_template()
        
        # Process each row in the DataFrame
        for _, row in df.iterrows():
            # Replace placeholders in the template with values from the row
            for prod_id in [1, 2, 3]:
                replace_placeholders(template_content, row, prod_id, orcid, data_dir)
            
            # Save the modified TOML content in a subdirectory named after the PDB
            #save_toml(row["PDB"], replaced_template, os.getcwd())
            
    print("TOML files updated successfully.")

if __name__ == "__main__":
    main()
