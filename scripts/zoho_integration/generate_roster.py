import hashlib
import json
import csv
import os

def generate_roster():
    # 1. Configuration
    input_file = os.path.join(os.path.dirname(__file__), 'raw_emails.csv')
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'public')
    output_file = os.path.join(output_dir, 'iff-roster.json')

    # Using an environment variable for the salt, with a fallback for testing
    salt = os.environ.get('IFF_ROSTER_SALT', 'iff_secret_2026')

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    hashed_roster = []

    try:
        # 2. Read raw emails from CSV
        with open(input_file, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Assuming the column name is 'Email' or similar
                email = row.get('Email') or row.get('email')
                if not email:
                    continue

                # 3. Normalize: Lowercase and strip whitespace
                clean_email = email.strip().lower()

                # 4. Salt
                salted_email = f"{clean_email}+{salt}"

                # 5. Hash (SHA-256)
                email_hash = hashlib.sha256(salted_email.encode('utf-8')).hexdigest()
                hashed_roster.append(email_hash)

        # 6. Output to static site build folder
        with open(output_file, 'w') as f:
            json.dump({"valid_hashes": hashed_roster}, f, indent=2)

        print(f"Successfully generated hashed roster with {len(hashed_roster)} entries.")
        print(f"Output saved to: {output_file}")

    except Exception as e:
        print(f"Error generating roster: {e}")

if __name__ == "__main__":
    generate_roster()
