#!/bin/bash

# List changed and untracked files
changed_files=$(git status --porcelain -uall | awk '{print $2}' | grep -v '/.*/.*/.*/.*.json'
)

# Initialize counters
krets_count=0
kommune_count=0
fylke_count=0
nasjonalt_count=0

# Loop through file names and count keywords
for f in $changed_files; do
  [[ $f == */krets/* ]]      && ((krets_count++))
  [[ $f == */kommune/* ]]    && ((kommune_count++))
  [[ $f == */fylke/* ]]      && ((fylke_count++))
  [[ $f == */nasjonalt/* ]]  && ((nasjonalt_count++))
done

# Print summary
#echo "Changed files:"
#echo "$changed_files"
echo "nasjonalt: $nasjonalt_count | fylke: $fylke_count | kommune: $kommune_count | krets: $krets_count"
