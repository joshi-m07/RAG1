from typing import Any, Dict, List, Optional, Tuple

import os
import requests


def get_base_url() -> str:
	return os.getenv("API_BASE_URL", "http://localhost:8000")


def _handle_response(resp: requests.Response) -> Tuple[Optional[Any], Optional[str]]:
	try:
		resp.raise_for_status()
	except requests.HTTPError as e:
		try:
			data = resp.json()
			err_msg = data.get("detail") if isinstance(data, dict) else str(data)
		except Exception:
			err_msg = resp.text or str(e)
		return None, err_msg
	try:
		if resp.status_code == 204:
			return True, None
		return resp.json(), None
	except Exception:
		return None, "Invalid JSON response"


def add_task(api_base_url: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
	url = f"{api_base_url.rstrip('/')}/tasks"
	try:
		resp = requests.post(url, json=payload, timeout=10)
		return _handle_response(resp)
	except requests.RequestException as e:
		return None, str(e)


def get_tasks(api_base_url: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
	url = f"{api_base_url.rstrip('/')}/tasks"
	try:
		resp = requests.get(url, timeout=10)
		data, err = _handle_response(resp)
		if err:
			return [], err
		return data or [], None
	except requests.RequestException as e:
		return [], str(e)


def update_task(api_base_url: str, task_id: Any, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
	url = f"{api_base_url.rstrip('/')}/tasks/{task_id}"
	try:
		resp = requests.put(url, json=payload, timeout=10)
		return _handle_response(resp)
	except requests.RequestException as e:
		return None, str(e)


def delete_task(api_base_url: str, task_id: Any) -> Tuple[bool, Optional[str]]:
	url = f"{api_base_url.rstrip('/')}/tasks/{task_id}"
	try:
		resp = requests.delete(url, timeout=10)
		ok, err = _handle_response(resp)
		return bool(ok), err
	except requests.RequestException as e:
		return False, str(e)


def get_tasks_today(api_base_url: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
	url = f"{api_base_url.rstrip('/')}/tasks/today"
	try:
		resp = requests.get(url, timeout=10)
		data, err = _handle_response(resp)
		if err:
			return [], err
		return data or [], None
	except requests.RequestException as e:
		return [], str(e)


