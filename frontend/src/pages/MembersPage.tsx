import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Users2 } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { extractApiError, fetchMembers, updateMember } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";

const ROLES = ["manager", "team_head", "member", "client"];

export default function MembersPage() {
  const qc = useQueryClient();
  const toast = useToast();

  const membersQ = useQuery({
    queryKey: ["members"],
    queryFn: fetchMembers,
  });

  const mut = useMutation({
    mutationFn: (args: {
      userId: number;
      role?: string;
      teamId?: number | null;
    }) =>
      updateMember(args.userId, {
        role: args.role,
        team_id: args.teamId,
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["members"] });
      toast.success(
        vars.role ? "Role updated" : "Team assignment updated",
      );
    },
    onError: (err) => toast.error("Update failed", extractApiError(err)),
  });

  if (membersQ.isError) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">Members</h1>
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {extractApiError(membersQ.error)}
        </div>
      </div>
    );
  }

  const teams = membersQ.data?.teams ?? [];
  const members = membersQ.data?.members ?? [];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Members
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Assign team membership and roles. Manager only.
        </p>
      </header>

      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <Users2 className="h-4 w-4" /> Team roster
            </span>
          }
          description={`${members.length} user${members.length === 1 ? "" : "s"}`}
        />
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 text-left font-medium">User</th>
                  <th className="px-5 py-3 text-left font-medium">Email</th>
                  <th className="px-5 py-3 text-left font-medium">Team</th>
                  <th className="px-5 py-3 text-left font-medium">Role</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {membersQ.isLoading ? (
                  <tr>
                    <td colSpan={4} className="px-5 py-8 text-center text-slate-500">
                      Loading members…
                    </td>
                  </tr>
                ) : members.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-5 py-8 text-center text-slate-500">
                      No members yet.
                    </td>
                  </tr>
                ) : (
                  members.map((m) => (
                    <tr key={m.id} className="bg-white">
                      <td className="px-5 py-3 font-medium text-slate-900">
                        {m.username}
                      </td>
                      <td className="px-5 py-3 text-slate-600">{m.email}</td>
                      <td className="px-5 py-3">
                        <select
                          value={m.team_id ?? ""}
                          onChange={(e) =>
                            mut.mutate({
                              userId: m.id,
                              teamId: e.target.value
                                ? Number(e.target.value)
                                : null,
                            })
                          }
                          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
                        >
                          <option value="">No team</option>
                          {teams.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <select
                            value={m.role}
                            onChange={(e) =>
                              mut.mutate({ userId: m.id, role: e.target.value })
                            }
                            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
                          >
                            {ROLES.map((r) => (
                              <option key={r} value={r}>
                                {r}
                              </option>
                            ))}
                          </select>
                          <Badge tone="muted">{m.role}</Badge>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
