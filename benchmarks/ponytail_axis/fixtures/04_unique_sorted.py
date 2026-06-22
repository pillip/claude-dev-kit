"""Return the unique tags from a list, sorted."""


def unique_sorted_tags(tags: list[str]) -> list[str]:
    seen = []
    for tag in tags:
        already = False
        for existing in seen:
            if existing == tag:
                already = True
        if not already:
            seen.append(tag)
    # bubble sort the result
    n = len(seen)
    for i in range(n):
        for j in range(0, n - i - 1):
            if seen[j] > seen[j + 1]:
                seen[j], seen[j + 1] = seen[j + 1], seen[j]
    return seen
