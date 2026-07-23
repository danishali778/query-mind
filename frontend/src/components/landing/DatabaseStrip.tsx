import { L } from './tokens';

const DATABASES = [
  { name: 'PostgreSQL', dot: L.indigo.base },
  { name: 'MySQL', dot: '#f59e0b' },
  { name: 'Snowflake', dot: L.sky.light },
  { name: 'BigQuery', dot: L.sky.deep },
  { name: 'SQL Server', dot: '#ef4444' },
  { name: 'SQLite', dot: L.emerald.base },
];

export function DatabaseStrip() {
  return (
    <section
      style={{
        position: 'relative',
        zIndex: 1,
        maxWidth: 1180,
        margin: '0 auto',
        padding: '52px clamp(20px, 4vw, 48px) 76px',
        textAlign: 'center',
      }}
    >
      <p
        className="reveal"
        data-reveal
        style={{
          fontSize: 12.5,
          fontWeight: 800,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: L.text3,
          margin: '0 0 24px',
        }}
      >
        Connects to the databases you already run
      </p>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
        {DATABASES.map((db, i) => (
          <div
            key={db.name}
            className="reveal landing-db-chip"
            data-reveal
            data-reveal-delay={40 + i * 50}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 9,
              background: L.surface,
              border: `1px solid ${L.border}`,
              borderRadius: 12,
              padding: '11px 18px',
              fontFamily: L.fontMono,
              fontSize: 13.5,
              fontWeight: 600,
              color: L.text2,
              boxShadow: L.raised,
            }}
          >
            <span style={{ width: 9, height: 9, borderRadius: 3, background: db.dot }} />
            {db.name}
          </div>
        ))}
      </div>
    </section>
  );
}
