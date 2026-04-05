import os
import logging

logger = logging.getLogger(__name__)


class AccountManager:
    """
    Manages multiple Seedream accounts loaded from numbered env vars:

        ACCOUNT_1_EMAIL, ACCOUNT_1_PASSWORD
        ACCOUNT_2_EMAIL, ACCOUNT_2_PASSWORD
        ...

    Falls back to the legacy EMAIL / PASSWORD pair if no numbered accounts
    are found, so existing single-account setups continue to work.
    """

    def __init__(self):
        self._accounts = self._load_accounts()
        self._index = 0

        if not self._accounts:
            raise ValueError(
                "No accounts configured. Add ACCOUNT_1_EMAIL / ACCOUNT_1_PASSWORD "
                "(and optionally ACCOUNT_2_*, ACCOUNT_3_*, ...) to your .env file."
            )

        logger.info(
            f"AccountManager: {len(self._accounts)} account(s) loaded. "
            f"Starting with: {self._accounts[0]['email']}"
        )

    def _load_accounts(self):
        accounts = []
        n = 1
        while True:
            email = os.getenv(f"ACCOUNT_{n}_EMAIL")
            password = os.getenv(f"ACCOUNT_{n}_PASSWORD")
            if not email or not password:
                break
            accounts.append({"email": email, "password": password})
            n += 1

        if not accounts:
            # Fallback: legacy single-account env vars
            email = os.getenv("EMAIL")
            password = os.getenv("PASSWORD")
            if email and password:
                logger.debug("Using legacy EMAIL/PASSWORD env vars as single account.")
                accounts.append({"email": email, "password": password})

        return accounts

    @property
    def current(self) -> dict:
        """Returns the active account as {email, password}."""
        return self._accounts[self._index]

    @property
    def state_path(self) -> str:
        """Returns the Playwright session file for the active account."""
        return f"state_{self._index}.json"

    @property
    def count(self) -> int:
        return len(self._accounts)

    @property
    def exhausted(self) -> bool:
        return self._index >= len(self._accounts)

    def rotate(self) -> bool:
        """
        Advance to the next account.
        Returns True if a new account is available, False if all are exhausted.
        """
        next_index = self._index + 1
        if next_index >= len(self._accounts):
            logger.warning("All accounts exhausted — no more accounts to rotate to.")
            return False

        self._index = next_index
        logger.info(
            f"Rotated to account [{self._index + 1}/{len(self._accounts)}]: "
            f"{self._accounts[self._index]['email']}"
        )
        return True
