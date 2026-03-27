import json

def fix_json_quotes(input_filepath, output_filepath):
    """Reads a file with Python-style single quotes in a dictionary/list,
    converts them to double quotes to be valid JSON, and writes to a new file."""
    try:
        with open(input_filepath, 'r') as infile:
            content = infile.read()
            # Attempt to evaluate the content as a Python literal
            data = eval(content)
            # Convert the Python object back to a JSON string with double quotes
            json_string = json.dumps(data, indent=4) # indent for readability
        with open(output_filepath, 'w') as outfile:
            outfile.write(json_string)
        print(f"Successfully converted quotes from '{input_filepath}' to '{output_filepath}'")
    except FileNotFoundError:
        print(f"Error: Input file '{input_filepath}' not found.")
    except SyntaxError as e:
        print(f"Error: Syntax error in input file '{input_filepath}'. It might not be a valid Python literal: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    input_file = "data/mapped_results/BloodCalcification-NoMore.txt"
    output_file = "data/mapped_results/BloodCalcification-NoMore_fixed.json" # Create a new file to be safe
    fix_json_quotes(input_file, output_file)

    # After running, replace the original with the fixed one if you're sure it's correct
    # import os
    # os.replace(output_file, input_file)
