file_path="./core/node.py"

if [ -z "$file_path" ]; then
    echo "Usage: $0 <file>"
    exit 1
fi

# Use grep to find lines containing "params" or "self.params" at the beginning of a word
# -o option only prints the matched parts of a line
variable_list=$(grep -oE '\b(self\.)?params[a-zA-Z0-9_]*' "$file_path")

# Print the list of variables
echo "List of variables:"
echo "$variable_list"