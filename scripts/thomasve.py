from prefect import Flow
from tasks.echo import echo_word

ECHO_TERM = "TEST"

@Flow
def main():
    echo_word(ECHO_TERM)

if __name__ == '__main__':
    main()
