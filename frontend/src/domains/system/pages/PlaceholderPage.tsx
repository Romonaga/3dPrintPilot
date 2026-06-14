type PlaceholderPageProps = {
  title: string;
};

export default function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <section className="panel placeholder-page">
      <h2>{title}</h2>
      <p>This domain is scaffolded and ready for implementation.</p>
    </section>
  );
}

