# cpu_test.py — safe CPU work
def is_prime(n):
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True

def main():
    limit = 20000  # moderate work
    s = 0
    for i in range(2, limit):
        if is_prime(i):
            s += i
    print("sum_primes_up_to", limit, s)

if __name__ == "__main__":
    main()
