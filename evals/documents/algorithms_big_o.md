# Algorithms and Big-O (Computer Science notes)

Big-O notation describes how running time grows with input size n in the worst case.

| Algorithm | Time complexity | Notes |
|---|---|---|
| Binary search | O(log n) | Requires sorted data; halves the search range each step |
| Linear search | O(n) | Checks every element |
| Bubble sort | O(n^2) | Repeatedly swaps adjacent items; simple but slow |
| Merge sort | O(n log n) | Divide and conquer; needs O(n) extra space |
| Hash table lookup | O(1) average | O(n) worst case when many keys collide |

Binary search is O(log n) because every comparison discards half of the remaining elements, so at most
log2(n) comparisons are needed. Merge sort splits the list in half repeatedly (log n levels) and merges each
level in linear time, giving O(n log n). Bubble sort compares every pair in the worst case, giving O(n^2).
