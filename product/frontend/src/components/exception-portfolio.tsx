import type { WorkspaceData } from "@/lib/product-workspace";
import { portfolio } from "@/lib/exception-workbench";
import { money } from "@/lib/financial";

export function ExceptionPortfolio({ data }: { data: WorkspaceData }) {
  const breakdown = portfolio(data),
    total = data.assessments.items.length;
  return (
    <section
      className="p-card p-portfolio"
      aria-label="Financial exception reporting"
    >
      <div className="p-section-heading">
        <div>
          <p className="p-eyebrow">FINANCE OPERATIONS</p>
          <h2>Exception portfolio</h2>
        </div>
        <span className="p-subtle-tag">No currency conversion</span>
      </div>
      <div className="p-portfolio-grid">
        <div className="p-state-distribution">
          <h3>Loaded assessment states</h3>
          <p>
            {total} of {data.assessments.total} assessments loaded. Counts are
            records, not unique invoices.
          </p>
          {breakdown.states.length ? (
            breakdown.states.map(([label, count]) => (
              <div className="p-state-row" key={label}>
                <span>{label}</span>
                <strong>{count}</strong>
                <div className="p-meter">
                  <span
                    style={{ width: `${total ? (count / total) * 100 : 0}%` }}
                  />
                </div>
              </div>
            ))
          ) : (
            <p>No assessment states available.</p>
          )}
        </div>
        <div className="p-currency-report">
          <h3>Currency coverage</h3>
          <div className="p-table-scroll">
            <table className="p-table">
              <caption className="sr-only">
                Backend potential amounts and loaded assessment counts per
                currency
              </caption>
              <thead>
                <tr>
                  <th>Currency</th>
                  <th>Current potential</th>
                  <th>Loaded</th>
                  <th>Confirmed</th>
                  <th>Awaiting review</th>
                </tr>
              </thead>
              <tbody>
                {breakdown.currencies.map(([currency, row]) => (
                  <tr key={currency}>
                    <th scope="row">{currency}</th>
                    <td className="p-money">
                      {data.summary.potential_by_currency[currency] !==
                      undefined
                        ? money(
                            data.summary.potential_by_currency[currency],
                            currency,
                          )
                        : "Not returned"}
                    </td>
                    <td>{row.count}</td>
                    <td>{row.confirmed}</td>
                    <td>{row.waiting}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>
            Amounts come from the backend summary
            {data.summary.limited ? " (latest 1,000 evaluations only)" : ""}.
            State counts use loaded records. Potential amounts are not recovered
            funds.
          </p>
        </div>
      </div>
    </section>
  );
}
