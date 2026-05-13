import json
import os
import re
import subprocess
import sys

import numpy as np


def parse_xvg(filepath):
    data = []
    if not os.path.exists(filepath):
        return data
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith(("#", "@")):
                continue
            cols = line.split()
            if cols:
                data.append([float(c) for c in cols])
    return data


def xvg_stats(filepath, col_idx):
    data = parse_xvg(filepath)
    if not data:
        return None, None, data
    vals = [row[col_idx] for row in data if len(row) > col_idx]
    if not vals:
        return None, None, data
    return float(np.mean(vals)), float(np.std(vals)), data


def list_energy_terms(edr_path, cwd, gmx_bin="gmx"):
    cmd = [gmx_bin, "energy", "-f", edr_path, "-o", "_tmp_list.xvg"]
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    stdout, _ = proc.communicate(input="0\n")

    mapping = {}
    for line in stdout.splitlines():
        m = re.search(r"^\s*(\d+)\s+(.+?)\s*$", line)
        if not m:
            continue
        idx = int(m.group(1))
        name = m.group(2).strip().lower()
        mapping[name] = idx
    return mapping


def resolve_term_indices(term_mapping, requested_terms):
    indices = []
    for term in requested_terms:
        key = term.lower()
        if key in term_mapping:
            indices.append(term_mapping[key])
            continue

        matched = None
        for name, idx in term_mapping.items():
            if key in name:
                matched = idx
                break
        if matched is None:
            return None
        indices.append(matched)
    return indices


def run_energy(edr_path, output_xvg, requested_terms, cwd, gmx_bin="gmx"):
    term_mapping = list_energy_terms(edr_path, cwd, gmx_bin)
    indices = resolve_term_indices(term_mapping, requested_terms)
    if not indices:
        return False

    cmd = [gmx_bin, "energy", "-f", edr_path, "-o", output_xvg]
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    input_str = "\n".join(str(i) for i in indices) + "\n0\n"
    proc.communicate(input=input_str)
    return proc.returncode == 0


def validate(input_data):
    phase = input_data.get("phase")
    files = input_data.get("files", {})
    cwd = input_data.get("cwd", os.getcwd())
    gmx_bin = input_data.get("gmx_bin", os.environ.get("GMX_BIN", "gmx"))

    edr = files.get("edr")
    log_file = files.get("log")

    if edr and not os.path.isabs(edr):
        edr = os.path.join(cwd, edr)
    if log_file and not os.path.isabs(log_file):
        log_file = os.path.join(cwd, log_file)

    verdict = "WARNING"
    reason = "Unable to determine"
    recommendation = "Check files manually."
    metrics = {}

    try:
        if phase == "minim":
            fmax = None
            if log_file and os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if "Maximum force" in line:
                            parts = line.split("=")
                            if len(parts) > 1:
                                fmax = float(parts[1].strip().split()[0])

            if fmax is None:
                verdict = "FAIL"
                reason = "Could not find Fmax in log file."
            elif fmax < 1000:
                metrics["fmax"] = fmax
                verdict = "PASS"
                reason = f"Fmax ({fmax}) is below 1000 kJ/mol/nm."
            elif fmax <= 5000:
                metrics["fmax"] = fmax
                verdict = "WARNING"
                reason = f"Fmax ({fmax}) is between 1000 and 5000."
                recommendation = "Proceed with caution or tighten minimization."
            else:
                metrics["fmax"] = fmax
                verdict = "FAIL"
                reason = f"Fmax ({fmax}) is above 5000."
                recommendation = "Increase nsteps or decrease emstep, then retry."

        elif phase == "nvt":
            xvg_name = "energy_nvt.xvg"
            ok = run_energy(edr, xvg_name, ["Temperature"], cwd, gmx_bin)
            temp_avg, temp_std, _ = xvg_stats(os.path.join(cwd, xvg_name), 1)

            if not ok or temp_avg is None:
                verdict = "FAIL"
                reason = "Temperature data not found."
            else:
                metrics["temperature_avg"] = temp_avg
                metrics["temperature_std"] = temp_std
                if temp_std < 5:
                    verdict = "PASS"
                    reason = f"Temperature is stable (std: {temp_std:.3f} < 5K)."
                elif temp_std < 10:
                    verdict = "WARNING"
                    reason = f"Temperature std is {temp_std:.3f} (5-10K)."
                else:
                    verdict = "FAIL"
                    reason = f"Temperature fluctuation too high (std: {temp_std:.3f} > 10K)."
                    recommendation = "Reduce tau_t to 0.05 and retry."

        elif phase == "npt":
            xvg_name = "energy_npt.xvg"
            ok = run_energy(edr, xvg_name, ["Pressure", "Density"], cwd, gmx_bin)
            xvg_path = os.path.join(cwd, xvg_name)
            p_avg, p_std, data = xvg_stats(xvg_path, 1)
            d_avg = d_std = None
            if data and len(data[0]) > 2:
                d_avg, d_std, _ = xvg_stats(xvg_path, 2)

            if not ok or d_avg is None:
                verdict = "FAIL"
                reason = "Density data not found."
            else:
                metrics["pressure_avg"] = p_avg
                metrics["pressure_std"] = p_std
                metrics["density_avg"] = d_avg
                metrics["density_std"] = d_std

                if 950 <= d_avg <= 1050:
                    verdict = "PASS"
                    reason = f"Density ({d_avg:.3f}) is within 950-1050 kg/m^3."
                elif 900 <= d_avg <= 1100:
                    verdict = "WARNING"
                    reason = f"Density ({d_avg:.3f}) is slightly off target."
                else:
                    verdict = "FAIL"
                    reason = f"Density ({d_avg:.3f}) is out of acceptable range."
                    recommendation = "Adjust tau_p or extend NPT simulation."

        elif phase == "md":
            xvg_name = "energy_md.xvg"
            ok = run_energy(edr, xvg_name, ["Potential", "Total Energy"], cwd, gmx_bin)
            data = parse_xvg(os.path.join(cwd, xvg_name))

            if not ok or not data or len(data[0]) < 3:
                verdict = "FAIL"
                reason = "Energy data extraction failed."
            else:
                t = [row[0] for row in data]
                e_tot = [row[2] for row in data]
                z = np.polyfit(t, e_tot, 1)
                slope = float(z[0])
                metrics["total_energy_drift_slope"] = slope

                if abs(slope) < 1.0:
                    verdict = "PASS"
                    reason = f"Total energy is stable (slope: {slope:.3f})."
                else:
                    verdict = "WARNING"
                    reason = f"Total energy shows drift (slope: {slope:.3f})."
                    recommendation = "Check PME settings or timestep."

        return {
            "verdict": verdict,
            "phase": phase,
            "metrics": metrics,
            "reason": reason,
            "recommendation": recommendation,
        }
    except Exception as e:
        return {"verdict": "FAIL", "reason": str(e), "phase": phase}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1].startswith("{"):
            input_data = json.loads(sys.argv[1])
        else:
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                input_data = json.load(f)
    else:
        input_data = json.loads(sys.stdin.read())

    result = validate(input_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
