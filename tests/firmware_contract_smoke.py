#!/usr/bin/env python3
"""Black-box guard for the modern OpenSprinkler App firmware contract."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SUPPORTED_FWV = 221
MIN_SUPPORTED_FWM = 4
DEFAULT_PASSWORD_HASH = "a6d82bced638de3def1e9bbb4983225c"
SPECIAL_STATION_DEFINITION = "010101010101"
READ_ENDPOINTS = ("jo", "ja", "jc", "jn", "je", "jp", "js")
VERSION_ONLY_AUTH_ENDPOINTS = ("jo", "ja")


class ContractError(AssertionError):
	"""Raised when a response no longer satisfies the App contract."""


def require(condition: bool, message: str) -> None:
	if not condition:
		raise ContractError(message)


def require_object(value: Any, label: str) -> dict[str, Any]:
	require(isinstance(value, dict), f"{label} must be a JSON object")
	return value


def require_keys(value: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
	missing = [key for key in keys if key not in value]
	require(not missing, f"{label} is missing required fields: {', '.join(missing)}")


def require_int(value: Any, label: str, minimum: int = 0, maximum: int | None = None) -> int:
	require(isinstance(value, int) and not isinstance(value, bool), f"{label} must be an integer")
	require(value >= minimum, f"{label} must be at least {minimum}")
	if maximum is not None:
		require(value <= maximum, f"{label} must be at most {maximum}")
	return value


def require_list(value: Any, label: str) -> list[Any]:
	require(isinstance(value, list), f"{label} must be an array")
	return value


def validate_controller(value: Any) -> dict[str, Any]:
	controller = require_object(value, "/jc")
	require_keys(controller, (
		"devt", "nbrd", "en", "sn1", "sn2", "rd", "rdst", "sunrise", "sunset",
		"eip", "lwc", "lswc", "lupt", "lrbtc", "lrun", "pq", "pt", "nq", "ocs",
		"mac", "loc", "jsp", "wsp", "ifkey", "dname", "wto", "mqtt", "wtdata",
		"wterr", "wtrestr", "wls", "sbits", "ps", "gpio",
	), "/jc")
	boards = require_int(controller["nbrd"], "/jc.nbrd", 1, 25)
	require_int(controller["devt"], "/jc.devt")
	for key in ("en", "sn1", "sn2", "rd", "pq", "wtrestr"):
		require_int(controller[key], f"/jc.{key}", 0, 1)
	for key in ("rdst", "lwc", "lswc", "lupt"):
		require_int(controller[key], f"/jc.{key}")
	for key in ("sunrise", "sunset"):
		require_int(controller[key], f"/jc.{key}", 0, 1440)
	require(isinstance(controller["eip"], (int, str)), "/jc.eip must be a number or string")
	for key in ("wto", "mqtt", "wtdata"):
		require_object(controller[key], f"/jc.{key}")
	require_int(controller["wterr"], "/jc.wterr", -(2**31), 2**31 - 1)
	require(len(require_list(controller["lrun"], "/jc.lrun")) == 4,
		"/jc.lrun must contain [station, program, duration, endtime]")
	levels = require_list(controller["wls"], "/jc.wls")
	require(all(isinstance(item, int) and 0 <= item <= 250 for item in levels),
		"/jc.wls values must be integer percentages from 0 to 250")
	station_bits = require_list(controller["sbits"], "/jc.sbits")
	require(len(station_bits) == boards + 1 and station_bits[-1] == 0,
		"/jc.sbits must contain one byte per board and a trailing zero")
	statuses = require_list(controller["ps"], "/jc.ps")
	require(len(statuses) == boards * 8, "/jc.ps station count must match /jc.nbrd")
	for index, status in enumerate(statuses):
		require(isinstance(status, list) and len(status) == 4,
			f"/jc.ps[{index}] must contain [program, remaining, start, group]")
	return controller


def validate_options(value: Any, expected_fwf: str) -> dict[str, Any]:
	options = require_object(value, "/jo")
	require_keys(options, (
		"fwv", "fwm", "fwf", "hwv", "hwt", "mexp", "tz", "hp0", "hp1", "sdt",
		"mas", "mton", "mtof", "mas2", "mton2", "mtof2", "ms", "wl", "uwt", "den",
		"ipas", "devid", "lg", "dim", "sar", "ife", "ife2", "sn1t", "sn1o", "sn1on",
		"sn1of",
	), "/jo")
	require(options["fwv"] == SUPPORTED_FWV,
		f"/jo.fwv must remain the upstream-compatible App epoch {SUPPORTED_FWV}")
	require_int(options["fwm"], "/jo.fwm", MIN_SUPPORTED_FWM)
	require(options["fwf"] == expected_fwf, f"/jo.fwf must equal {expected_fwf!r}")
	for key in ("hwv", "hwt", "mexp", "tz", "hp0", "hp1", "wl", "uwt", "sn1t"):
		require_int(options[key], f"/jo.{key}")
	require_list(options["ms"], "/jo.ms")
	return options


def validate_stations(value: Any) -> dict[str, Any]:
	stations = require_object(value, "/jn")
	board_fields = ("masop", "masop2", "ignore_rain", "ignore_sn1", "ignore_sn2", "stn_dis", "stn_spe")
	require_keys(stations, board_fields + ("stn_grp", "snames", "maxlen"), "/jn")
	names = require_list(stations["snames"], "/jn.snames")
	require(len(names) >= 8 and len(names) % 8 == 0 and all(isinstance(name, str) for name in names),
		"/jn.snames must contain one string per configured station")
	boards = len(names) // 8
	for key in board_fields:
		values = require_list(stations[key], f"/jn.{key}")
		require(len(values) == boards, f"/jn.{key} must contain one byte per board")
	groups = require_list(stations["stn_grp"], "/jn.stn_grp")
	require(len(groups) == len(names), "/jn.stn_grp station count must match /jn.snames")
	require_int(stations["maxlen"], "/jn.maxlen", 1, 255)
	return stations


def validate_special_stations(value: Any, station_count: int) -> dict[str, Any]:
	special = require_object(value, "/je")
	for station_id, definition in special.items():
		require(station_id.isdecimal() and int(station_id) < station_count,
			f"/je station id {station_id!r} is invalid")
		entry = require_object(definition, f"/je.{station_id}")
		require_keys(entry, ("st", "sd"), f"/je.{station_id}")
		require_int(entry["st"], f"/je.{station_id}.st", 0, 6)
		require(isinstance(entry["sd"], str), f"/je.{station_id}.sd must be a string")
	return special


def validate_programs(value: Any, station_count: int) -> dict[str, Any]:
	programs = require_object(value, "/jp")
	require_keys(programs, ("nprogs", "nboards", "mnp", "mnst", "pnsize", "pd"), "/jp")
	count = require_int(programs["nprogs"], "/jp.nprogs", 0, 255)
	require_int(programs["mnp"], "/jp.mnp", 1, 255)
	require(programs["mnst"] == 4, "/jp.mnst must retain four start-time slots")
	require_int(programs["pnsize"], "/jp.pnsize", 1, 255)
	require(require_int(programs["nboards"], "/jp.nboards", 1, 25) * 8 == station_count,
		"/jp.nboards must agree with /jn.snames")
	rows = require_list(programs["pd"], "/jp.pd")
	require(len(rows) == count, "/jp.nprogs must match /jp.pd length")
	for index, row in enumerate(rows):
		require(isinstance(row, list) and len(row) == 7, f"/jp.pd[{index}] must be a seven-field tuple")
		require(isinstance(row[3], list) and len(row[3]) == 4,
			f"/jp.pd[{index}] must retain four start-time slots")
		require(isinstance(row[4], list) and len(row[4]) == station_count,
			f"/jp.pd[{index}] durations must match the configured stations")
		require(isinstance(row[5], str), f"/jp.pd[{index}] name must be a string")
		require(isinstance(row[6], list) and len(row[6]) == 3,
			f"/jp.pd[{index}] date range must contain three fields")
	return programs


def validate_status(value: Any, station_count: int) -> dict[str, Any]:
	status = require_object(value, "/js")
	require_keys(status, ("sn", "nstations"), "/js")
	require(status["nstations"] == station_count, "/js.nstations must agree with /jn.snames")
	states = require_list(status["sn"], "/js.sn")
	require(len(states) == station_count and all(item in (0, 1) for item in states),
		"/js.sn must contain one binary value per station")
	return status


def read_identity(repo: Path) -> tuple[int, int, str]:
	defines = (repo / "defines.h").read_text(encoding="utf-8")

	def match(pattern: str, label: str) -> str:
		import re

		found = re.search(pattern, defines, re.MULTILINE)
		require(found is not None, f"could not read {label} from defines.h")
		return found.group(1)

	fwv = int(match(r"^#define\s+OS_FW_VERSION\s+([0-9]+)\b", "OS_FW_VERSION"))
	fwm = int(match(r"^#define\s+OS_FW_MINOR\s+([0-9]+)\b", "OS_FW_MINOR"))
	fork_id = match(r'^#define\s+OSF_FORK_ID\s+"([^"]+)"', "OSF_FORK_ID")
	fork_build = int(match(r"^#define\s+OSF_FORK_BUILD\s+([0-9]+)\b", "OSF_FORK_BUILD"))
	return fwv, fwm, f"{fork_id}.{fork_build}"


def get_json(
	port: int,
	endpoint: str,
	password: str,
	parameters: dict[str, str] | None = None,
) -> tuple[int, Any]:
	query_parameters = {"pw": password}
	if parameters:
		query_parameters.update(parameters)
	query = urllib.parse.urlencode(query_parameters)
	request = urllib.request.Request(
		f"http://127.0.0.1:{port}/{endpoint}?{query}",
		headers={"Connection": "close"},
	)
	try:
		with urllib.request.urlopen(request, timeout=3) as response:
			body = response.read().decode("utf-8")
			return response.status, json.loads(body)
	except urllib.error.HTTPError as error:
		body = error.read().decode("utf-8")
		return error.code, json.loads(body)


def wait_until_ready(process: subprocess.Popen[bytes], port: int) -> None:
	deadline = time.monotonic() + 15
	while time.monotonic() < deadline:
		if process.poll() is not None:
			raise ContractError(f"DEMO firmware exited before serving requests (status {process.returncode})")
		try:
			get_json(port, "jo", "invalid")
			return
		except (ConnectionError, OSError, TimeoutError, ValueError):
			time.sleep(0.1)
	raise ContractError(f"DEMO firmware did not listen on port {port} within 15 seconds")


def exercise_contract(repo: Path, binary: Path, port: int) -> None:
	fwv, fwm, expected_fwf = read_identity(repo)
	require(fwv == SUPPORTED_FWV,
		f"OS_FW_VERSION must remain {SUPPORTED_FWV}; fork identity belongs in OSF_FORK_*/fwf")
	require(fwm >= MIN_SUPPORTED_FWM, f"OS_FW_MINOR must be at least {MIN_SUPPORTED_FWM}")

	with tempfile.TemporaryDirectory(prefix="opensprinkler-contract-") as data_dir, tempfile.TemporaryFile() as log:
		process = subprocess.Popen(
			[str(binary), "-d", data_dir],
			cwd=repo,
			stdout=log,
			stderr=subprocess.STDOUT,
		)
		try:
			wait_until_ready(process, port)

			for endpoint in READ_ENDPOINTS:
				status, payload = get_json(port, endpoint, "invalid")
				require(status == 200, f"/{endpoint} auth failure must retain HTTP 200 compatibility")
				if endpoint in VERSION_ONLY_AUTH_ENDPOINTS:
					require(payload == {"fwv": fwv},
						f"/{endpoint} auth failure must be the exact version-only bootstrap shape")
				else:
					require(payload == {"result": 2, "item": ""},
						f"/{endpoint} auth failure must be the standard unauthorized result shape")

			# Use only the disposable DEMO data directory to force a non-empty /je. This
			# proves the st/sd wire keys and type range instead of accepting {} alone.
			status, payload = get_json(port, "cs", DEFAULT_PASSWORD_HASH, {
				"sid": "0",
				"st": "1",
				"sd": SPECIAL_STATION_DEFINITION,
				"p0": "1",
			})
			require(status == 200 and payload == {"result": 1, "item": ""},
				"DEMO special-station fixture setup failed")

			responses: dict[str, Any] = {}
			for endpoint in READ_ENDPOINTS:
				status, payload = get_json(port, endpoint, DEFAULT_PASSWORD_HASH)
				require(status == 200, f"/{endpoint} success must return HTTP 200")
				responses[endpoint] = payload

			options = validate_options(responses["jo"], expected_fwf)
			controller = validate_controller(responses["jc"])
			stations = validate_stations(responses["jn"])
			station_count = len(stations["snames"])
			require(controller["nbrd"] * 8 == station_count, "/jc and /jn station counts must agree")
			special = validate_special_stations(responses["je"], station_count)
			require(special.get("0") == {"st": 1, "sd": SPECIAL_STATION_DEFINITION},
				"/je must retain the st/sd fields for a configured special station")
			validate_programs(responses["jp"], station_count)
			validate_status(responses["js"], station_count)

			aggregate = require_object(responses["ja"], "/ja")
			require_keys(aggregate, ("settings", "programs", "options", "status", "stations"), "/ja")
			aggregate_options = validate_options(aggregate["options"], expected_fwf)
			aggregate_controller = validate_controller(aggregate["settings"])
			aggregate_stations = validate_stations(aggregate["stations"])
			aggregate_count = len(aggregate_stations["snames"])
			require(aggregate_controller["nbrd"] * 8 == aggregate_count,
				"/ja settings and stations counts must agree")
			validate_programs(aggregate["programs"], aggregate_count)
			validate_status(aggregate["status"], aggregate_count)
			for key in ("fwv", "fwm", "fwf"):
				require(aggregate_options[key] == options[key], f"/ja.options.{key} must match /jo.{key}")
		finally:
			process.terminate()
			try:
				process.wait(timeout=3)
			except subprocess.TimeoutExpired:
				process.kill()
				process.wait(timeout=3)


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--binary", type=Path, required=True, help="authenticated DEMO firmware binary")
	parser.add_argument("--port", type=int, required=True, help="HTTP_PORT compiled into the DEMO binary")
	args = parser.parse_args()

	repo = Path(__file__).resolve().parents[1]
	binary = args.binary if args.binary.is_absolute() else (repo / args.binary)
	require(binary.is_file(), f"firmware binary does not exist: {binary}")
	require(1 <= args.port <= 65535, "--port must be from 1 to 65535")
	exercise_contract(repo, binary.resolve(), args.port)
	print("Firmware contract smoke passed for /jo, /ja, /jc, /jn, /je, /jp, and /js.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
