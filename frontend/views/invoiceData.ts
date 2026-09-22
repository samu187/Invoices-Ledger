// API amounts remain decimal strings; these helpers only format or compare them.
export type Invoice = {
  id: number; supplier_id: number; number: string; date: string; supplier: string; currency: string;
  total: string; paid: string; balance: string; vat_rate: string;
  exchange_rate: string; rate_date: string; base_currency: string;
  base_net: string; base_vat: string; base_total: string; base_balance: string;
  expense_accounts: string[]; has_invoice_posting: boolean;
};

export function money(value: string) {
  const [whole, fraction = ''] = value.split('.');
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`;
}

export function isZero(value: string) {
  return /^-?0(?:\.0+)?$/.test(value);
}

export function status(invoice: Invoice) {
  if (!invoice.has_invoice_posting) return 'Missing posting';
  if (isZero(invoice.balance)) return isZero(invoice.base_balance) ? 'Paid' : 'GBP residual';
  return isZero(invoice.paid) ? 'Unpaid' : 'Part-paid';
}

// Round the saved positive rate for display only, using decimal digits.
export function rateDisplay(value: string) {
  const [whole, fraction = ''] = value.split('.');
  const digits = fraction.padEnd(5, '0');
  let units = BigInt(whole) * 10000n + BigInt(digits.slice(0, 4));
  if (digits[4] >= '5') units += 1n;
  return `${units / 10000n}.${(units % 10000n).toString().padStart(4, '0')}`;
}

export function nextInvoiceNumber(invoices: Pick<Invoice, 'supplier_id' | 'number'>[], supplierId: number) {
  let highest = 0n;
  let width = 3;
  for (const invoice of invoices) {
    if (invoice.supplier_id !== supplierId || !/^\d+$/.test(invoice.number)) continue;
    const value = BigInt(invoice.number);
    if (value >= highest) {
      highest = value;
      width = Math.max(3, invoice.number.length);
    }
  }
  return (highest + 1n).toString().padStart(width, '0');
}
