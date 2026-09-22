// 1. Imports
import { useEffect, useState } from 'react';
import { Alert, Anchor, Button, Group, ScrollArea, Select, Stack, Table, Tabs, Text, TextInput, Title } from '@mantine/core';
import InvoiceForm from '../components/InvoiceForm';
import InvoiceDetail from '../components/InvoiceDetail';
import { type Invoice, money, isZero } from './invoiceData';

export default function Invoices({ initialInvoiceId, onOpenJournal, onOpenPayment }: { initialInvoiceId: number | null; onOpenJournal: (id: number) => void; onOpenPayment: (id: number) => void }) {
  // 2. State
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [currency, setCurrency] = useState<string | null>('All currencies');
  const [filter, setFilter] = useState<string | null>('Outstanding');
  const [selectedId, setSelectedId] = useState<number | null>(initialInvoiceId);

  const [adding, setAdding] = useState(false);
  const [revision, setRevision] = useState(0);

  // 3. Effects
  useEffect(() => {
    let active = true;
    setError('');
    async function loadInvoices() {
      try {
        const response = await fetch('/api/invoices');
        if (!response.ok) throw new Error(`Could not load invoices (${response.status}).`);
        const data: Invoice[] = await response.json();
        if (active) setInvoices(data);
      } catch (error) {
        if (active) setError(error instanceof Error ? error.message : 'Could not load invoices.');
      }
    }
    loadInvoices();
    return () => { active = false; };
  }, [revision]);

  // 4. Filtering (balances and totals come from the API)
  const query = search.trim().toLowerCase();
  const rows = (invoices ?? []).filter((invoice) =>
    `${invoice.supplier} ${invoice.number}`.toLowerCase().includes(query) &&
    (currency === 'All currencies' || invoice.currency === currency) &&
    (filter === 'All' || (filter === 'Paid'
      ? invoice.has_invoice_posting && isZero(invoice.balance) && isZero(invoice.base_balance)
      : !invoice.has_invoice_posting || !isZero(invoice.balance) || !isZero(invoice.base_balance))),
  ).sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id);

  // 5. View: keeping the list mounted preserves filters when returning
  if (adding) return <InvoiceForm onBack={() => setAdding(false)} onCreated={(id) => { setAdding(false); setSelectedId(id); setRevision(revision + 1); }} />;
  if (selectedId !== null) return <InvoiceDetail key={selectedId} id={selectedId} onBack={() => setSelectedId(null)} onOpenJournal={onOpenJournal} onOpenPayment={onOpenPayment} />;

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={1} size="h2">Invoices</Title>
        <Button onClick={() => setAdding(true)}>+ Add invoice</Button>
      </Group>
      <Group align="end">
        <TextInput label="Search invoices" placeholder="Supplier or invoice number" value={search} onChange={(event) => setSearch(event.currentTarget.value)} style={{ flex: 1 }} miw={200} />
        <Select label="Currency" data={['All currencies', 'GBP', 'EUR', 'USD']} value={currency} onChange={setCurrency} allowDeselect={false} w={180} />
      </Group>
      <Tabs value={filter} onChange={setFilter}>
        <Tabs.List>{['Outstanding', 'Paid', 'All'].map((label) => <Tabs.Tab key={label} value={label}>{label}</Tabs.Tab>)}</Tabs.List>
      </Tabs>
      {error ? <Alert color="red" title="Invoices unavailable">{error} Refresh to retry.</Alert> : !invoices ? <Text role="status">Loading invoices…</Text> : (
        <>
          <ScrollArea>
            <Table highlightOnHover miw={850} verticalSpacing="sm">
              <Table.Thead><Table.Tr>{['Date', 'Invoice', 'Supplier', 'Currency'].map((label) => <Table.Th key={label}>{label}</Table.Th>)}{['Total', 'Paid', 'Outstanding'].map((label) => <Table.Th key={label} ta="right">{label}</Table.Th>)}</Table.Tr></Table.Thead>
              <Table.Tbody>{rows.map((invoice) => (
                <Table.Tr key={invoice.id} onClick={() => setSelectedId(invoice.id)} style={{ cursor: 'pointer' }}>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>{invoice.date}</Table.Td>
                  <Table.Td><Anchor component="button" size="sm" onClick={() => setSelectedId(invoice.id)}>{invoice.number}</Anchor></Table.Td>
                  <Table.Td>{invoice.supplier}</Table.Td><Table.Td>{invoice.currency}</Table.Td>
                  <Table.Td ta="right">{money(invoice.total)}</Table.Td><Table.Td ta="right">{money(invoice.paid)}</Table.Td><Table.Td ta="right" fw={600}>{money(invoice.balance)}</Table.Td>
                </Table.Tr>
              ))}</Table.Tbody>
            </Table>
          </ScrollArea>
          {rows.length === 0 && <Text c="dimmed">{invoices.length === 0 ? 'No invoices recorded yet.' : 'No invoices match these filters.'}</Text>}
          <Text size="xs" c="dimmed">{rows.length} of {invoices.length} invoices · Amounts are in each invoice’s currency.</Text>
        </>
      )}
    </Stack>
  );
}
