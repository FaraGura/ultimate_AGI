#UnifiedCoreV11\inspect_conceptnet.py
import csv

INPUT_FILE = "assertions.csv"

def main():
    count = 0
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            uri_start = row[0].strip()
            uri_rel = row[1].strip()
            uri_end = row[2].strip()

            if "/c/ru/" in uri_start or "/c/ru/" in uri_end:
                print(f"START: {uri_start}")
                print(f"REL:   {uri_rel}")
                print(f"END:   {uri_end}")
                print("---")
                count += 1
                if count >= 20:
                    break

if __name__ == "__main__":
    main()