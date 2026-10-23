import type { ServerAccessUser } from "@/api/queries"
import {
  Avatar,
  AvatarFallback,
  AvatarGroup,
  AvatarGroupCount,
} from "@/components/ui/avatar"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { initials } from "@/lib/functions"
import { cn } from "@/lib/utils"

const MAX_VISIBLE = 4

const ACCESS_LABEL: Record<ServerAccessUser["access"], string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Shared",
}

function displayName(user: ServerAccessUser) {
  return user.full_name ?? user.username ?? "Unknown user"
}

/** Avatars of everyone who can see a server: owner, admins and members. */
export function ServerAccessAvatars({
  users,
}: {
  users: Array<ServerAccessUser>
}) {
  if (users.length === 0) {
    return <span className="text-xs text-muted-foreground">—</span>
  }

  const visible = users.slice(0, MAX_VISIBLE)
  const hidden = users.slice(MAX_VISIBLE)

  return (
    <AvatarGroup>
      {visible.map((user) => (
        <Tooltip key={user.user_id}>
          <TooltipTrigger asChild>
            <Avatar
              className={cn(
                user.role === "editor"
                  ? "after:border-blue-200 dark:after:border-blue-600"
                  : user.role === "admin"
                    ? "after:border-destructive/10"
                    : ""
              )}
            >
              <AvatarFallback
                className={cn(
                  "text-xs font-medium",
                  user.role === "editor"
                    ? "bg-blue-50 text-blue-600 dark:bg-blue-950"
                    : user.role === "admin"
                      ? "bg-red-50 text-destructive dark:bg-red-950"
                      : ""
                )}
              >
                {initials(user.username)}
              </AvatarFallback>
            </Avatar>
          </TooltipTrigger>
          <TooltipContent>
            {displayName(user)} · {ACCESS_LABEL[user.access]}
          </TooltipContent>
        </Tooltip>
      ))}
      {hidden.length > 0 && (
        <Tooltip>
          <TooltipTrigger asChild>
            <AvatarGroupCount>
              <span className="text-xs font-medium text-muted-foreground">
                +{hidden.length}
              </span>
            </AvatarGroupCount>
          </TooltipTrigger>
          <TooltipContent>
            <div className="flex flex-col gap-0.5">
              {hidden.map((user) => (
                <span key={user.user_id}>
                  {displayName(user)} · {ACCESS_LABEL[user.access]}
                </span>
              ))}
            </div>
          </TooltipContent>
        </Tooltip>
      )}
    </AvatarGroup>
  )
}
