// 1. Imports and API response types (money stays as decimal strings)
import { useEffect, useState } from 'react';
import { Alert, Anchor, Breadcrumbs, Divider, Group, Kbd, ScrollArea, Stack, Table, Text, Title, Tooltip } from '@mantine/core';
import JournalEntry from '../components/JournalEntry';

type Account = { code: string; name: string; account_type: string; balance: string };
type TrialBalance = {
  rows: (Account & { debit: string; credit: string })[];
  total_debit: string;
  total_credit: string;
  balanced: boolean;
};
type AccountDetail = Account & {
  transactions: {
    entry_id: number; posting_date: string; description: string;
    invoice_id: number | null; payment_id: number | null;
    debit: string; credit: string; balance: string;
  }[];
};

export default function Accounts({ initialAccountCode = null, initialJournalId, onOpenInvoice }: { initialAccountCode?: string | null; initialJournalId: number | null; onOpenInvoice: (id: number) => void }) {
  // 2. State
  const [selectedCode, setSelectedCode] = useState(initialAccountCode);
  const [journalId, setJournalId] = useState<number | null>(initialJournalId);
  const [trialBalance, setTrialBalance] = useState<TrialBalance | null>(null);
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [trialError, setTrialError] = useState('');
  const [accountError, setAccountError] = useState('');

  // 3. Effects: ignore responses after unmount or a different account selection
  useEffect(() => {
    if (journalId === null) return;
    function handleBack(event: KeyboardEvent) {
      const target = event.target;
      if (event.defaultPrevented || event.isComposing || event.key !== 'Escape' || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (target instanceof HTMLElement && (target.isContentEditable || target.closest('input, textarea, select, [role="textbox"]'))) return;
      event.preventDefault();
      setJournalId(null);
    }
    window.addEventListener('keydown', handleBack);
    return () => window.removeEventListener('keydown', handleBack);
  }, [journalId]);

  useEffect(() => {
    let active = true;
    async function loadTrialBalance() {
      try {
        const response = await fetch('/api/accounts/trial-balance');
        if (!response.ok) throw new Error(`Could not load trial balance (${response.status}).`);
        const data: TrialBalance = await response.json();
        if (active) setTrialBalance(data);
      } catch (error) {
        if (active) setTrialError(error instanceof Error ? error.message : 'Could not load trial balance.');
      }
    }
    loadTrialBalance();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setAccount(null);
    setAccountError('');
    if (selectedCode === null) return;
    async function loadAccount() {
      try {
        const response = await fetch(`/api/accounts/${selectedCode}`);
        if (!response.ok) throw new Error(`Could not load account ${selectedCode} (${response.status}).`);
        const data: AccountDetail = await response.json();
        if (active) setAccount(data);
      } catch (error) {
        if (active) setAccountError(error instanceof Error ? error.message : 'Could not load account.');
      }
    }
    loadAccount();
    return () => { active = false; };
  }, [selectedCode]);

  // 4. Helpers: selection and display only, no financial calculations
  function openJournal(id: number) {
    setJournalId(id);
  }

  function selectAccount(code: string) {
    setSelectedCode(code);
    setJournalId(null);
  }

  function money(value: string) {
    const [whole, fraction = ''] = value.replace(/^-/, '').split('.');
    return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`;
  }

  function balance(value: string) {
    if (/^-?0(?:\.0+)?$/.test(value)) return '0.00';
    return `${money(value)} ${value.startsWith('-') ? 'Cr' : 'Dr'}`;
  }

  // 5. View
  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={1} size="h2">Accounts</Title>
        <Text size="sm" c="dimmed">All time · All amounts in GBP</Text>
      </Group>

      {/* A stable top panel keeps the ledger below in place when switching views. */}
      <Stack h={450} gap="md">
        {journalId !== null ? (
          <>
            <Group justify="space-between">
              <Breadcrumbs separator="/">
                <Tooltip label="Back to account balances · Esc" withArrow>
                  <Anchor component="button" size="sm" underline="hover" aria-label="Back to account balances" aria-keyshortcuts="Escape" onClick={() => setJournalId(null)}>
                    ‹ Balances
                  </Anchor>
                </Tooltip>
                <Text size="sm" fw={600}>Journal #{journalId}</Text>
              </Breadcrumbs>
              <Tooltip label="Back to account balances"><Kbd size="xs">Esc</Kbd></Tooltip>
            </Group>
            <ScrollArea style={{ flex: 1, minHeight: 0 }}>
              <JournalEntry key={journalId} id={journalId} accountCode={selectedCode ?? ''} onSelectAccount={selectAccount} onOpenInvoice={onOpenInvoice} />
            </ScrollArea>
          </>
        ) : (
          <>
            <Group justify="space-between">
              <Title order={2} size="md" c="dimmed">— Balances —</Title>
              {trialBalance && !trialBalance.balanced && <Text size="sm" c="red">Debits and credits do not balance</Text>}
            </Group>
            {trialError ? <Alert color="red" title="Trial balance unavailable">{trialError} Refresh the page to retry.</Alert> : !trialBalance ? <Text role="status">Loading trial balance…</Text> : (
              <>
                <ScrollArea.Autosize mah={400}>
                  <Table verticalSpacing={3} highlightOnHover stickyHeader miw={560} style={{ fontVariantNumeric: 'tabular-nums' }}>
                    <Table.Thead><Table.Tr><Table.Th>Code</Table.Th><Table.Th>Account</Table.Th><Table.Th ta="right">Debit</Table.Th><Table.Th ta="right">Credit</Table.Th></Table.Tr></Table.Thead>
                    <Table.Tbody>
                      {trialBalance.rows.map((row) => (
                        <Table.Tr key={row.code} bg={selectedCode === row.code ? '#edf1f6' : undefined} onClick={() => selectAccount(row.code)} style={{ cursor: 'pointer' }}>
                          <Table.Td><Anchor component="button" size="sm" aria-label={`Select account ${row.code}`} aria-pressed={selectedCode === row.code} onClick={() => selectAccount(row.code)}>{row.code}</Anchor></Table.Td>
                          <Table.Td>{row.name}</Table.Td>
                          <Table.Td ta="right">{money(row.debit)}</Table.Td><Table.Td ta="right">{money(row.credit)}</Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                    <Table.Tfoot><Table.Tr><Table.Th colSpan={2}>Total</Table.Th><Table.Th ta="right">{money(trialBalance.total_debit)}</Table.Th><Table.Th ta="right">{money(trialBalance.total_credit)}</Table.Th></Table.Tr></Table.Tfoot>
                  </Table>
                </ScrollArea.Autosize>
                {trialBalance.rows.length === 0 && <Text c="dimmed">No accounts found.</Text>}
              </>
            )}

          </>
        )}
      </Stack>

      <Divider my="md" color="indigo.1" />

      <Title order={2} size="sm" c="dimmed">— Account ledger —</Title>

      {selectedCode === null ? <Text c="dimmed">Select an account in Balances to view its ledger.</Text> : accountError ? <Alert color="red" title="Account unavailable">{accountError} Refresh the page to retry.</Alert> : !account || account.code !== selectedCode ? <Text role="status">Loading account {selectedCode}…</Text> : (
        <Stack gap="sm">
          <Group justify="space-between">
            <div>
              <Title order={2} size="h4">{account.code} — {account.name}</Title>
              <Text size="sm" c="dimmed">{account.account_type} · Opening balance: GBP 0.00</Text>
            </div>
            <Text fw={600}>Closing balance: GBP {balance(account.balance)}</Text>
          </Group>
          <ScrollArea.Autosize mah={360}>
            <Table highlightOnHover stickyHeader miw={800} style={{ fontVariantNumeric: 'tabular-nums' }}>
              <Table.Thead><Table.Tr><Table.Th>Date</Table.Th><Table.Th>Journal</Table.Th><Table.Th>Description</Table.Th><Table.Th>Source</Table.Th><Table.Th ta="right">Debit</Table.Th><Table.Th ta="right">Credit</Table.Th><Table.Th ta="right">Balance</Table.Th></Table.Tr></Table.Thead>
              <Table.Tbody>
                {account.transactions.map((row, index) => (
                  <Table.Tr key={`${row.entry_id}-${index}`} bg={row.entry_id === journalId ? '#edf1f6' : undefined} onClick={() => openJournal(row.entry_id)} style={{ cursor: 'pointer' }}>
                    <Table.Td style={{ whiteSpace: 'nowrap' }}>{row.posting_date}</Table.Td>
                    <Table.Td><Anchor component="button" size="sm" aria-label={`Open journal entry ${row.entry_id}`} onClick={() => openJournal(row.entry_id)}>#{row.entry_id}</Anchor></Table.Td><Table.Td>{row.description}</Table.Td>
                    <Table.Td>{[row.invoice_id !== null && `Invoice #${row.invoice_id}`, row.payment_id !== null && `Payment #${row.payment_id}`].filter(Boolean).join(' · ') || '—'}</Table.Td>
                    <Table.Td ta="right">{money(row.debit)}</Table.Td><Table.Td ta="right">{money(row.credit)}</Table.Td><Table.Td ta="right" style={{ whiteSpace: 'nowrap' }}>{balance(row.balance)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea.Autosize>
          {account.transactions.length === 0 && <Text c="dimmed">No transactions for this account.</Text>}
        </Stack>
      )}
    </Stack>
  );
}
