import { TemporaryAccountSummary, listAccounts } from "@/lib/api";

export const VAULT_CACHE_KEY = "accounts";

export interface VaultData {
  accounts: TemporaryAccountSummary[];
  total: number;
}

/** One shared fetcher so the Identity Vault and Mailboxes pages use the same cache entry. */
export async function fetchVault(): Promise<VaultData> {
  const page = await listAccounts();
  return { accounts: page.results, total: page.count };
}
