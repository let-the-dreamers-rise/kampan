"""DynamoDB table with a string partition key `pk`, a string sort key `sk` and TTL on `ttl`."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.repo.table import ConditionFailed, Item, live


def _to_db(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, dict):
        return {k: _to_db(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_db(v) for v in value]
    return value


def _from_db(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _from_db(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_db(v) for v in value]
    return value


class DynamoTable:
    def __init__(self, name: str, resource=None) -> None:
        import boto3
        from boto3.dynamodb.conditions import Attr, Key

        self._t = (resource or boto3.resource("dynamodb")).Table(name)
        self._attr, self._key = Attr, Key
        self._errors = self._t.meta.client.exceptions

    def get(self, pk: str, sk: str) -> Item | None:
        found = self._t.get_item(Key={"pk": pk, "sk": sk}, ConsistentRead=True).get("Item")
        return live(_from_db(found)) if found else None

    def put(self, item: Item, if_absent: bool = False) -> None:
        kwargs: dict[str, Any] = {"Item": _to_db(item)}
        if if_absent:
            kwargs["ConditionExpression"] = "attribute_not_exists(pk)"
        try:
            self._t.put_item(**kwargs)
        except self._errors.ConditionalCheckFailedException as exc:
            raise ConditionFailed(str(exc)) from exc

    def update(self, pk: str, sk: str, values: Item, expect: Item | None = None) -> Item:
        names = {f"#v{i}": k for i, k in enumerate(values)}
        vals = {f":v{i}": _to_db(v) for i, v in enumerate(values.values())}
        cond = "attribute_exists(pk)"
        for j, (k, v) in enumerate((expect or {}).items()):
            names[f"#e{j}"] = k
            vals[f":e{j}"] = _to_db(v)
            cond += f" AND #e{j} = :e{j}"
        try:
            out = self._t.update_item(Key={"pk": pk, "sk": sk},
                                      UpdateExpression="SET " + ", ".join(f"#v{i} = :v{i}" for i in range(len(values))),
                                      ConditionExpression=cond, ExpressionAttributeNames=names,
                                      ExpressionAttributeValues=vals, ReturnValues="ALL_NEW")
        except self._errors.ConditionalCheckFailedException as exc:
            raise ConditionFailed(str(exc)) from exc
        return _from_db(out["Attributes"])

    def add(self, pk: str, sk: str, field: str, amount: int = 1, ttl: int | None = None) -> int:
        expr, names, vals = "ADD #f :n", {"#f": field}, {":n": amount}
        if ttl is not None:
            expr += " SET #t = if_not_exists(#t, :t)"
            names["#t"], vals[":t"] = "ttl", ttl
        out = self._t.update_item(Key={"pk": pk, "sk": sk}, UpdateExpression=expr, ExpressionAttributeNames=names,
                                  ExpressionAttributeValues=vals, ReturnValues="UPDATED_NEW")
        return int(out["Attributes"][field])

    def query(self, pk: str, prefix: str = "", limit: int = 100, newest_first: bool = False) -> list[Item]:
        cond = self._key("pk").eq(pk)
        if prefix:
            cond = cond & self._key("sk").begins_with(prefix)
        out = self._t.query(KeyConditionExpression=cond, Limit=limit, ScanIndexForward=not newest_first,
                            ConsistentRead=True)
        return [i for i in (live(_from_db(x)) for x in out.get("Items", [])) if i is not None]

    def delete(self, pk: str, sk: str) -> None:
        self._t.delete_item(Key={"pk": pk, "sk": sk})
