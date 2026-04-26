"use client"

import { Dialog } from "@/components/ui/Dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useModuleManagerStore } from "@/lib/store/moduleManager"

export function ModuleManager() {
  const { isOpen, close } = useModuleManagerStore()

  return (
    <Dialog
      open={isOpen}
      onClose={close}
      title="Module Manager"
      description="Configure which modules appear in your workspace tab bar."
      size="md"
      className="max-w-[640px]"
    >
      <Tabs defaultValue="active">
        <TabsList className="w-full">
          <TabsTrigger value="active" className="flex-1">
            Active
          </TabsTrigger>
          <TabsTrigger value="available" className="flex-1">
            Available
          </TabsTrigger>
          <TabsTrigger value="premium" className="flex-1">
            Premium
          </TabsTrigger>
          <TabsTrigger value="custom" className="flex-1">
            Custom
          </TabsTrigger>
        </TabsList>

        <TabsContent value="active" className="mt-4 min-h-[200px]">
          <div className="text-sm text-muted-foreground">Active</div>
        </TabsContent>

        <TabsContent value="available" className="mt-4 min-h-[200px]">
          <div className="text-sm text-muted-foreground">Available</div>
        </TabsContent>

        <TabsContent value="premium" className="mt-4 min-h-[200px]">
          <div className="text-sm text-muted-foreground">Premium</div>
        </TabsContent>

        <TabsContent value="custom" className="mt-4 min-h-[200px]">
          <div className="text-sm text-muted-foreground">
            Custom modules coming soon — contact your admin to request a custom module.
          </div>
        </TabsContent>
      </Tabs>
    </Dialog>
  )
}
