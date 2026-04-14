# Instrucciones para Claude Code

## Estilo de respuesta

- Respuestas cortas y precisas. Sin párrafos largos.
- Solo código y comentarios esenciales.
- Bullet points > prosa. Tablas > explicaciones.
- No repitas lo que ya dije. No pidas confirmación obvia.
- Si algo no está claro, pregunta una vez, directo.

## Contexto del workspace

Investigación de mercado 2026 + specs técnicas para proyectos AWS/Cloud/IA/DevOps (freelance internacional, empleo remoto senior).

## Docs de referencia (leer antes de implementar)

| Doc | Contenido |
|-----|-----------|
| `docs/CONTEXT.md` | Mercado 2026, fuentes, resumen ejecutivo |
| `docs/OPPORTUNITIES.md` | 8 oportunidades rankeadas |
| `docs/PROJECT-A.md` | GenAI Security Gateway + RAG Assistant |
| `docs/PROJECT-B.md` | Platform Engineering Kit (EKS/Backstage/GitOps) |
| `docs/PROJECT-C.md` | FinOps Autopilot (opcional) |
| `docs/ARCHITECTURE.md` | Repo structure, CI/CD, IaC, K8s patterns |
| `docs/SECURITY.md` | Seguridad, compliance, licencias OSS |
| `docs/ROADMAP.md` | Roadmap 12 semanas |

## Herramientas de optimización

| Recurso | Ubicación |
|---------|-----------|
| MCP config (context7 + sequential-thinking) | `instructions/mcp-config-example.json` |
| Token optimization guide | `instructions/claude-code-optimization/` |
| claudectx CLI | `instructions/claudectx/` |
| All tools index | `instructions/README.md` |

## Reglas de implementación

1. **Stack**: AWS (Bedrock, EKS, ECR, S3, IAM, Secrets Manager), Terraform, GitHub Actions, Argo CD, OTel/ADOT.
2. **Monorepo**: `apps/ | packages/ | infra/ | gitops/ | .github/ | docs/ | scripts/`
3. **GitOps**: Argo CD; separar código app vs desired state en `gitops/`.
4. **Seguridad first**: OIDC, least privilege, SLSA, SBOM, guardrails, audit logs.
5. **IaC**: Terraform por defecto. CloudFormation solo si el cliente lo exige.
6. **Observabilidad**: OTel/ADOT + Container Insights.
7. **Coste**: Karpenter + Spot. Well-Architected Cost Optimization.
8. **Licencia**: Apache-2.0 (starter kits), MIT (libs pequeñas).
9. **MVP first**: demostrable lo antes posible.
10. **Idioma**: código en inglés, docs en español + inglés según audiencia.
11. **Ignorar**: ver `.claudeignore` en la raíz del proyecto.
