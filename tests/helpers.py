from __future__ import annotations


def delete_with_preview(client, resource_url: str, *, reason: str | None = None):
    preview = client.post(f"{resource_url}/delete-preview")
    assert preview.status_code == 200
    token = preview.json()["confirm_token"]
    return client.request(
        "DELETE",
        resource_url,
        json={"reason": reason, "confirm_token": token},
    )


def restore_with_preview(client, resource_url: str):
    preview = client.post(f"{resource_url}/restore-preview")
    assert preview.status_code == 200
    token = preview.json()["confirm_token"]
    return client.post(f"{resource_url}/restore", json={"confirm_token": token})
