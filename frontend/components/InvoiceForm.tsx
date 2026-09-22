// 1. Imports
import { useEffect, useRef, useState } from 'react';
import { Alert, Anchor, Button, Group, Paper, Select, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { type Invoice, nextInvoiceNumber } from '../views/invoiceData';

type Supplier = { id: number; name: string };
type Account = { code: string; name: string; account_type: string };

export default function InvoiceForm({ onBack, onCreated }: { onBack: () => void; onCreated: (id: number) => void }) {
  // 2. State
  const today = new Date();
  const todayString = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const submitting = useRef(false);
  const [supplier, setSupplier] = useState<string | null>(null);
  const [number, setNumber] = useState('');
  const [date, setDate] = useState<string | null>(todayString);
  const [currency, setCurrency] = useState<string | null>('GBP');
  const [expense, setExpense] = useState<string | null>(null);
  const [total, setTotal] = useState('');
  const [vat, setVat] = useState('20');

  // 3. Effects
  useEffect(() => {
    let active = true;
    async function loadOptions() {
      try {
        const responses = await Promise.all(['/api/suppliers', '/api/accounts', '/api/invoices'].map((url) => fetch(url)));
        if (responses.some((response) => !response.ok)) throw new Error('Could not load invoice options. Return to Invoices and try again.');
        const [supplierRows, accountRows, invoiceRows] = await Promise.all(responses.map((response) => response.json()));
        if (invoiceRows.some((invoice: Invoice) => !Number.isInteger(invoice.supplier_id))) {
          throw new Error('The server needs restarting to enable supplier-specific invoice numbers. Restart FastAPI, then reopen this form.');
        }
        if (active) {
          setSuppliers(supplierRows);
          setAccounts(accountRows.filter((account: Account) => account.account_type === 'expense'));
          setInvoices(invoiceRows);
        }
      } catch (error) {
        if (active) setLoadError(error instanceof Error ? error.message : 'Could not load invoice options.');
      } finally {
        if (active) setLoading(false);
      }
    }
    loadOptions();
    return () => { active = false; };
  }, []);

  // 4. Helpers
  function selectSupplier(value: string | null) {
    setSupplier(value);
    setNumber(value ? nextInvoiceNumber(invoices, Number(value)) : '');
  }

  async function recordInvoice(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    setError('');
    if (!supplier || !number.trim() || !date || !currency || !expense) {
      setError('Complete all invoice fields.');
      return;
    }
    if (!/^\d{1,16}(\.\d{1,2})?$/.test(total) || /^0+(\.0+)?$/.test(total)) {
      setError('Enter a positive total with up to two decimal places.');
      return;
    }
    if (!/^\d{1,3}(\.\d{1,2})?$/.test(vat) || Number(vat) > 100) {
      setError('VAT rate must be between 0 and 100, with up to two decimal places.');
      return;
    }
    submitting.current = true;
    setSaving(true);
    try {
      const response = await fetch('/api/invoices', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ supplier_id: Number(supplier), invoice_number: number.trim(), invoice_date: date, currency, expense_account_code: expense, total_amount: total, vat_rate: vat }),
      });
      if (!response.ok) {
        const data = await response.json();
        const detail = typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map((item: { msg: string }) => item.msg).join(' ') : 'Could not record invoice.';
        throw new Error(response.status === 409 ? 'This invoice conflicts with an existing record. Check the supplier and invoice number.' : detail);
      }
      const result: { invoice_id: number; journal_id: number } = await response.json();
      onCreated(result.invoice_id);
    } catch (error) {
      setError(error instanceof TypeError ? 'The response could not be confirmed. Check the invoice list before retrying; it may have been recorded.' : error instanceof Error ? error.message : 'Could not record invoice.');
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  }

  // 5. View
  return (
    <Stack gap="lg" maw={780}>
      <Anchor component="button" ta="left" size="sm" disabled={saving} onClick={onBack}>‹ Invoices</Anchor>
      <div><Title order={1} size="h2">Add invoice</Title><Text size="sm" c="dimmed">Record a supplier invoice and its accounting entry.</Text></div>
      {loading ? <Text role="status">Loading suppliers and accounts…</Text> : loadError ? <Alert color="red">{loadError}</Alert> : (
        <Paper withBorder radius="md" p={{ base: 'md', sm: 'xl' }}>
          <form onSubmit={recordInvoice}>
            <Stack gap="lg">
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <Select label="Supplier" placeholder="Select a supplier first" data={suppliers.map((row) => ({ value: String(row.id), label: `${row.name} · #${row.id}` }))} searchable required value={supplier} onChange={selectSupplier} disabled={saving} nothingFoundMessage="No suppliers found" />
                <TextInput label="Invoice number" placeholder="Select a supplier" value={number} onChange={(event) => setNumber(event.currentTarget.value)} disabled={!supplier || saving} required maxLength={100} />
                <DatePickerInput label="Invoice date" value={date} onChange={setDate} maxDate={todayString} required disabled={saving} />
                <Select label="Currency" data={['GBP', 'EUR', 'USD']} value={currency} onChange={setCurrency} allowDeselect={false} required disabled={saving} />
                <TextInput label={`Invoice total (${currency})`} description="VAT-inclusive amount" placeholder="0.00" inputMode="decimal" value={total} onChange={(event) => setTotal(event.currentTarget.value)} required disabled={saving} />
                <TextInput label="VAT rate (%)" description="Use 0 for no VAT" inputMode="decimal" value={vat} onChange={(event) => setVat(event.currentTarget.value)} required disabled={saving} />
              </SimpleGrid>
              <Select label="Expense account" placeholder="Select an expense account" data={accounts.map((row) => ({ value: row.code, label: `${row.code} — ${row.name}` }))} searchable value={expense} onChange={setExpense} required disabled={saving} nothingFoundMessage="No expense accounts found" />
              {currency !== 'GBP' && <Text size="sm" c="dimmed">The invoice-date reference rate will be looked up when you record the invoice.</Text>}
              {error && <Alert color="red" title="Invoice not confirmed">{error}</Alert>}
              <Group justify="flex-end"><Button variant="subtle" disabled={saving} onClick={onBack}>Cancel</Button><Button type="submit" loading={saving} disabled={!supplier || !expense || !date}>Record invoice</Button></Group>
            </Stack>
          </form>
        </Paper>
      )}
    </Stack>
  );
}
