if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <folder1> <folder2> ..."
    exit 1
fi

all_variables=""


# Use find to get a list of files in the specified folder
for folder in "$@"; do
    for file in "$folder"/*; do
        if [ -f "$file" ]; then        
            # Use grep to find lines containing "params" or "self.params" at the beginning of a word
            # -o option only prints the matched parts of a line
            variable_list=$(grep -oE '\b(self\.)?params[[:alnum:]._]*\b' "$file" | awk '{sub(/(self\.)?params/, ""); sub(/^\.+/, ""); if ($0 != "") print}')

            all_variables+="\n$variable_list"
        fi
    done
done

unique_variables=$(echo "$all_variables" | tr ' ' '\n' | sort -u)

IFS=$'\n' # Set Internal Field Separator to newline to iterate over lines

for variable in $unique_variables; do
    # Apply your own logic here
    # Example: Print the variable with some custom message

    var="$(echo $variable | tr a-z A-Z | tr . _)"

    echo "$var"
done