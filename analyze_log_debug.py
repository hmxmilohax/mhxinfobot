import sys
from analyze_log import analyze_log_file

def main(log_file_path):
    # Confirm the file path
    print(f"Log file path: {log_file_path}")
    
    try:
        # Call the analyze_log_file function from analyze_log module
        output = analyze_log_file(log_file_path)
        # Print the output result
        print(f"Analyze log output: {output}")
    except Exception as e:
        print(f"Error while analyzing log file: {e}")

if __name__ == "__main__":
    # Check if the correct number of arguments is provided
    if len(sys.argv) != 2:
        print("Usage: py.py log_file_path")
    else:
        log_file_path = sys.argv[1]
        main(log_file_path)
