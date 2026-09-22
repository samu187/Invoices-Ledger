// 1. Imports and API response types
import { useEffect, useState } from 'react';
import { Alert, Anchor, Box, Breadcrumbs, Divider, Group, Kbd, Paper, ScrollArea, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { type Invoice, isZero, money, rateDisplay } from '../views/invoiceData';

type Journal = {
  id: number; posting_date: string; kind: string; description: string;
  invoice_id: number | null; payment_id: number | null;
  lines: { code: string; name: string; debit: string; credit: string }[];
  total_debit: string; total_credit: string;
};
type Detail = Invoice & { journals: Journal[] };
type Statement = {
  rows: { date: string; reference: string; amount: string; balance: string; payables: string; base_balance: string }[];
};

export default function InvoiceDetail({ id, onBack, onOpenJournal, onOpenPayment }: { id: number; onBack: () => void; onOpenJournal: (id: number) => void; onOpenPayment: (id: number) => void }) {
  // 2. State
  const [invoice, setInvoice] = useState<Detail | null>(null);
  const [statement, setStatement] = useState<Statement | null>(null);
  const [error, setError] = useState('');
  const [statementError, setStatementError] = useState('');

  // 3. Effects
  useEffect(() => {
    let active = true;
    async function loadInvoice() {
      try {
        const response = await fetch(`/api/invoices/${id}`);
        if (!response.ok) throw new Error(`Could not load invoice (${response.status}).`);
        const data: Detail = await response.json();
        if (active) setInvoice(data);
      } catch (error) {
        if (active) setError(error instanceof Error ? error.message : 'Could not load invoice.');
      }
    }
    async function loadStatement() {
      try {
        const response = await fetch(`/api/invoices/${id}/payments`);
        if (!response.ok) throw new Error(`Could not load statement (${response.status}).`);
        const data: Statement = await response.json();
        if (active) setStatement(data);
      } catch (error) {
        if (active) setStatementError(error instanceof Error ? error.message : 'Could not load statement.');
      }
    }
    loadInvoice();
    loadStatement();
    return () => { active = false; };
  }, [id]);

  useEffect(() => {
    function handleBack(event: KeyboardEvent) {
      if (event.defaultPrevented || event.isComposing || event.key !== 'Escape' || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const target = event.target;
      if (target instanceof HTMLElement && (target.isContentEditable || target.closest('input, textarea, select, [role="textbox"]'))) return;
      event.preventDefault();
      onBack();
    }
    window.addEventListener('keydown', handleBack);
    return () => window.removeEventListener('keydown', handleBack);
  }, [onBack]);

  // 4. Helpers: connect statement payment references to payment records
  function journalFor(reference: string) {
    return invoice?.journals.find((entry) => reference === (entry.kind === 'invoice' ? `Invoice #${entry.invoice_id}` : `Payment #${entry.payment_id}`));
  }

  const recognition = invoice?.journals.find((entry) => entry.kind === 'invoice');
  const invoiceNumber = invoice && /^\d+$/.test(invoice.number) ? invoice.number.padStart(3, '0') : invoice?.number;

  // 5. View
  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Breadcrumbs>
          <Anchor component="button" size="sm" onClick={onBack}>‹ Invoices</Anchor>
          <Text size="sm">{invoice?.number ?? `Invoice #${id}`}</Text>
        </Breadcrumbs>
        <Kbd size="xs">Esc</Kbd>
      </Group>
      {error ? <Alert color="red" title="Invoice unavailable">{error} Return to the list and open it again to retry.</Alert> : !invoice ? <Text role="status">Loading invoice…</Text> : (
        <>
          <Paper withBorder radius="md" p={{ base: 'md', sm: 'xl' }}>
            <Stack gap="xl">
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xl">
                <Paper withBorder radius="md" p="lg">
                  <Title order={1} size="h2">{invoice.supplier}</Title>
                  <Text size="lg" fw={500} mt={4}>Invoice {invoiceNumber}</Text>
                  <Text size="sm" c="dimmed" mt={4}>{invoice.date}</Text>
                </Paper>
                <Stack gap="md">
                  <Paper withBorder radius="md" p="lg" ta="right">
                    <Text size="sm" c="dimmed">Tot Invoice</Text>
                    <Text size="xl" fw={600} mt="sm">{invoice.currency} {money(invoice.total)}</Text>
                  </Paper>
                  <Box ta="right" px="lg">
                    <Text size="sm" c="dimmed">Payables Balance</Text>
                    <Text size="xl" fw={600} mt="sm">{invoice.currency} {money(invoice.balance)}</Text>
                  </Box>
                </Stack>
              </SimpleGrid>
              {!invoice.has_invoice_posting && <Alert color="red">Invoice recognition posting is missing. GBP amounts cannot be relied on.</Alert>}
              {isZero(invoice.balance) && !isZero(invoice.base_balance) && <Alert color="orange">The invoice currency is settled, but a GBP carrying balance remains.</Alert>}

              <Box w="100%" maw={380} style={{ fontVariantNumeric: 'tabular-nums' }}>
                <Text size="sm" c="dimmed">{invoice.currency} FX Rate {rateDisplay(invoice.exchange_rate)}</Text>
                <Text size="xl" fw={600} mt={4} mb="lg">GBP {money(invoice.base_total)}</Text>
                <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', columnGap: 32, rowGap: 12, alignItems: 'baseline' }}>
                  <Text size="sm" c="dimmed">Expenses</Text>
                  <Text fw={500} ta="right">GBP {money(invoice.base_net)}</Text>
                  <Text size="sm" c="dimmed">VAT Rate</Text>
                  <Text fw={500} ta="right">{invoice.vat_rate.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '')}%</Text>
                  <Text size="sm" c="dimmed">VAT</Text>
                  <Text fw={500} ta="right">GBP {money(invoice.base_vat)}</Text>
                </div>
              </Box>

              {recognition && <Group justify="flex-end"><Anchor component="button" size="sm" onClick={() => onOpenJournal(recognition.id)}>Open invoice journal ↗</Anchor></Group>}
            </Stack>
          </Paper>
          <Divider my="sm" color="indigo.1" />
            <Stack gap="sm">
              <Title order={2} size="md" c="dimmed">— Payment statement —</Title>
              <Text size="xs" c="dimmed">Payment labels open their payment details. GBP movements release the original liability; they are not cash payments.</Text>
              {statementError ? <Alert color="red">{statementError}</Alert> : !statement ? <Text role="status">Loading statement…</Text> : (
                <ScrollArea>
                  <Table highlightOnHover miw={850}>
                    <Table.Thead><Table.Tr><Table.Th>Date</Table.Th><Table.Th>Transaction</Table.Th><Table.Th>CCY</Table.Th><Table.Th ta="right">Amount</Table.Th><Table.Th ta="right">Balance</Table.Th><Table.Th>Base CCY</Table.Th><Table.Th ta="right">Payables</Table.Th><Table.Th ta="right">Payables balance</Table.Th></Table.Tr></Table.Thead>
                    <Table.Tbody>{statement.rows.map((row) => {
                      const entry = journalFor(row.reference);
                      return (
                        <Table.Tr key={row.reference}>
                          <Table.Td>{row.date}</Table.Td><Table.Td>{entry?.payment_id ? <Anchor component="button" size="sm" onClick={() => onOpenPayment(entry.payment_id!)}>{row.reference}</Anchor> : row.reference}</Table.Td>
                          <Table.Td>{invoice.currency}</Table.Td><Table.Td ta="right">{money(row.amount)}</Table.Td><Table.Td ta="right">{money(row.balance)}</Table.Td><Table.Td>{invoice.base_currency}</Table.Td><Table.Td ta="right">{money(row.payables)}</Table.Td><Table.Td ta="right">{money(row.base_balance)}</Table.Td>
                        </Table.Tr>
                      );
                    })}</Table.Tbody>
                  </Table>
                </ScrollArea>
              )}
            </Stack>
        </>
      )}
    </Stack>
  );
}
