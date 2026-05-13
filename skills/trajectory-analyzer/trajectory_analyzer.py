import json
import os
import re
import subprocess
import sys

import numpy as np


def run_cmd(cmd, cwd, stdin_str=""):
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    stdout, _ = proc.communicate(input=stdin_str)
    return stdout, proc.returncode


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


def downsample(data, max_points=100):
    if not data or len(data) <= max_points:
        return data
    indices = np.linspace(0, len(data) - 1, max_points, dtype=int)
    return [data[i] for i in indices]


def parse_xvg_with_legend(filepath):
    data = []
    legend = {}
    if not os.path.exists(filepath):
        return data, legend

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            if line.startswith("@"):
                m = re.search(r'@\s+s(\d+)\s+legend\s+"(.+)"', line)
                if m:
                    series_index = int(m.group(1))
                    name = m.group(2).strip().lower()
                    legend[name] = series_index + 1
                continue
            cols = line.split()
            if cols:
                data.append([float(c) for c in cols])
    return data, legend


def list_energy_terms(edr_path, cwd, gmx_bin="gmx"):
    cmd = [gmx_bin, "energy", "-f", edr_path, "-o", "_tmp_energy_list.xvg"]
    stdout, _ = run_cmd(cmd, cwd, "0\n")
    mapping = {}
    for line in stdout.splitlines():
        m = re.search(r"^\s*(\d+)\s+(.+?)\s*$", line)
        if m:
            mapping[m.group(2).strip().lower()] = int(m.group(1))
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


def run_energy_with_terms(edr_path, out_xvg, requested_terms, cwd, gmx_bin="gmx"):
    term_mapping = list_energy_terms(edr_path, cwd, gmx_bin)
    indices = resolve_term_indices(term_mapping, requested_terms)
    if not indices:
        return False

    cmd = [gmx_bin, "energy", "-f", edr_path, "-o", out_xvg]
    input_str = "\n".join(str(i) for i in indices) + "\n0\n"
    _, rc = run_cmd(cmd, cwd, input_str)
    return rc == 0


def analyze(input_data):
    files = input_data.get("files", {})
    analyses = input_data.get("analyses", ["rmsd", "rmsf", "gyrate", "energy"])
    cwd = input_data.get("cwd", os.getcwd())
    gmx_bin = input_data.get("gmx_bin", os.environ.get("GMX_BIN", "gmx"))

    tpr = files.get("tpr", "md.tpr")
    xtc = files.get("xtc", "md.xtc")
    edr = files.get("edr", "md.edr")

    reports = {}
    downsampled_data = {}
    generated_files = []

    try:
        if "rmsd" in analyses:
            out_xvg = "rmsd.xvg"
            run_cmd([gmx_bin, "rms", "-s", tpr, "-f", xtc, "-o", out_xvg, "-tu", "ns"], cwd, "4\n4\n")
            data = parse_xvg(os.path.join(cwd, out_xvg))
            if data:
                generated_files.append(out_xvg)
                half = len(data) // 2
                if half > 0:
                    second_half = [row[1] for row in data[half:]]
                    rmsd_final_avg = np.mean(second_half) * 10
                    rmsd_std = np.std(second_half) * 10
                    reports["rmsd_final_avg_angstrom"] = round(float(rmsd_final_avg), 3)
                    reports["rmsd_std_angstrom"] = round(float(rmsd_std), 3)
                    reports["rmsd_plateau_reached"] = bool(rmsd_std < 0.5)
                ds = downsample(data, 100)
                downsampled_data["rmsd"] = [{"t": row[0], "val": row[1]} for row in ds]

        if "rmsf" in analyses:
            out_xvg = "rmsf.xvg"
            run_cmd([gmx_bin, "rmsf", "-s", tpr, "-f", xtc, "-o", out_xvg, "-res"], cwd, "4\n")
            data = parse_xvg(os.path.join(cwd, out_xvg))
            if data:
                generated_files.append(out_xvg)
                vals = [row[1] for row in data]
                reports["rmsf_core_max_nm"] = round(float(np.max(vals)), 3)
                reports["rmsf_avg_nm"] = round(float(np.mean(vals)), 3)
                ds = downsample(data, 100)
                downsampled_data["rmsf"] = [{"res": int(row[0]), "val": row[1]} for row in ds]

        if "gyrate" in analyses:
            out_xvg = "gyrate.xvg"
            run_cmd([gmx_bin, "gyrate", "-s", tpr, "-f", xtc, "-o", out_xvg], cwd, "1\n")
            data = parse_xvg(os.path.join(cwd, out_xvg))
            if data:
                generated_files.append(out_xvg)
                vals = [row[1] for row in data]
                reports["gyration_avg_nm"] = round(float(np.mean(vals)), 3)
                ds = downsample(data, 100)
                downsampled_data["gyrate"] = [{"t": row[0], "val": row[1]} for row in ds]

        if "energy" in analyses:
            out_xvg = "energy_md_analysis.xvg"
            ok = run_energy_with_terms(edr, out_xvg, ["Potential", "Total Energy", "Temperature", "Pressure", "Density"], cwd, gmx_bin)
            data, legend = parse_xvg_with_legend(os.path.join(cwd, out_xvg))
            if ok and data:
                generated_files.append(out_xvg)

                tot_col = legend.get("total energy") or legend.get("total-energy")
                pot_col = legend.get("potential")
                if tot_col is None and len(data[0]) > 2:
                    tot_col = 2
                if pot_col is None and len(data[0]) > 1:
                    pot_col = 1

                if tot_col is not None and len(data[0]) > tot_col:
                    t = [row[0] for row in data]
                    e_tot = [row[tot_col] for row in data]
                    if len(t) > 1:
                        z = np.polyfit(t, e_tot, 1)
                        reports["energy_drift_slope"] = round(float(z[0]), 4)
                        reports["energy_drift_detected"] = bool(abs(z[0]) > 1.0)

                ds = downsample(data, 100)
                energy_rows = []
                for row in ds:
                    item = {"t": row[0]}
                    if pot_col is not None and len(row) > pot_col:
                        item["pot"] = row[pot_col]
                    if tot_col is not None and len(row) > tot_col:
                        item["tot"] = row[tot_col]
                    energy_rows.append(item)
                downsampled_data["energy"] = energy_rows

        return {
            "status": "success",
            "reports": reports,
            "downsampled_data": downsampled_data,
            "generated_files": generated_files,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1].startswith("{"):
            input_data = json.loads(sys.argv[1])
        else:
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                input_data = json.load(f)
    else:
        input_data = json.loads(sys.stdin.read())

    result = analyze(input_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
